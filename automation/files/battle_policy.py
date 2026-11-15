"""Bounded, state-only battle decisions. This module never sends game input.

Learning stores observed enemy HP changes between submitted actions and a later
ready menu. Other combatants/status effects can contribute: these are estimates,
not a recovered damage formula or proof of causal damage.
"""
import hashlib
import json
import math
from pathlib import Path


def number(value):
    return type(value) in (int,float) and math.isfinite(value)


def battle_of(state):
    return state.get('battle',{}) if 'battle' in state else state


def opaque(value):
    if not isinstance(value,(str,int)) or isinstance(value,bool) or not str(value):return None
    return hashlib.sha256(str(value).encode()).hexdigest()


def item_id(item):
    return item.get('item_id',item.get('id'))


class BattlePlanner:
    """Pure policy with private bounded persistence in one monitored session.

    ``decide`` reserves a menu generation to prevent duplicate submissions, even
    across restart. Call ``note_result`` only after the bridge accepted an action;
    ``observe`` may be called on every subsequent state. Unknown/unsafe telemetry
    returns None. Back decisions contain ``back: True`` instead of option_index.
    """
    def __init__(self,session):
        self.session=Path(session)
        self.path=self.session/'battle-decisions.json'
        self.learning_path=self.session/'battle-learning.json'
        self.data={'version':1,'handled':[],'explored':[],'decisions':[],
                   'intent':None,'pending':None,'item_streak':None}
        self.learning={'version':1,'label':'Observed enemy HP loss; not a causal damage estimate',
                       'samples':{},'kill_bounds':{},'incoming':{}}
        self._load(self.path,self.data)
        self._load(self.learning_path,self.learning)
        for key in ('handled','explored','decisions'):
            if not isinstance(self.data.get(key),list):self.data[key]=[]
            self.data[key]=self.data[key][-128:]
        for key in ('samples','kill_bounds','incoming'):
            if not isinstance(self.learning.get(key),dict):self.learning[key]={}
        self._save()

    @staticmethod
    def _load(path,defaults):
        try:
            saved=json.loads(path.read_text())
            if isinstance(saved,dict):
                for key in defaults:
                    if key in saved:defaults[key]=saved[key]
        except (OSError,ValueError,TypeError):pass

    @staticmethod
    def _atomic(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix('.tmp')
        with temporary.open('w') as stream:
            temporary.chmod(0o600)
            json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')
        temporary.replace(path)

    def _save(self):
        for key in ('handled','explored','decisions'):self.data[key]=self.data[key][-128:]
        for collection in ('samples','kill_bounds','incoming'):
            samples=self.learning[collection]
            for key in list(samples)[:-128]:del samples[key]
        self._atomic(self.path,self.data);self._atomic(self.learning_path,self.learning)

    @staticmethod
    def _identity(battle):
        identifier=opaque(battle.get('battle_id'));token=opaque(battle.get('menu_token'))
        return (identifier,token) if identifier and token else None

    @staticmethod
    def _ready(state,battle):
        return (state.get('phase','world')=='world' and battle.get('active') is True
                and battle.get('telemetry_complete') is True and battle.get('command_ready') is True
                and not battle.get('transitioning') and not battle.get('submitted')
                and not battle.get('result_ready') and not battle.get('can_advance')
                and isinstance(battle.get('actor'),dict)
                and all(isinstance(battle.get(field,[]),list)
                        for field in ('options','fighters','enemy_groups','items','party')))

    @staticmethod
    def _options(battle):
        return [option for option in battle.get('options',[]) if isinstance(option,dict)
                and option.get('enabled') is True and type(option.get('index')) is int
                and option['index']>=0]

    @staticmethod
    def _key(actor,enemy,kind,skill=None):
        return json.dumps([actor,enemy,kind,skill],separators=(',',':'))

    def _mean(self,key):
        values=self.learning['samples'].get(key,[])
        values=[float(value) for value in values if number(value) and value>=0]
        return sum(values)/len(values) if values else None

    @staticmethod
    def _enemies(battle):
        groups=battle.get('enemy_groups',[])
        return [fighter for fighter in battle.get('fighters',[]) if isinstance(fighter,dict)
                and fighter.get('group') in groups and fighter.get('controlled') is not True
                and number(fighter.get('hp')) and fighter['hp']>0
                and fighter.get('group')!=(battle.get('actor') or {}).get('group')]

    def _damage_estimate(self,key):
        values=[float(v) for v in self.learning['samples'].get(key,[]) if number(v) and v>=0]
        hits=sorted(v for v in values if v>0)
        bounds=[float(v) for v in self.learning['kill_bounds'].get(key,[]) if number(v) and v>0]
        if hits:
            # A lower observed-hit quartile with a margin and observed misses.
            # This remains a confounded estimate, never a damage guarantee.
            return hits[math.floor((len(hits)-1)*.25)]*.9*len(hits)/len(values)
        if bounds:return min(bounds)*.9*len(bounds)/(len(bounds)+len(values))
        return 0. if values else None

    def _append_learning(self,collection,key,value):
        values=self.learning[collection].setdefault(key,[])
        values.append(float(value));self.learning[collection][key]=values[-16:]

    def observe(self,state):
        battle=battle_of(state);identity=self._identity(battle);pending=self.data.get('pending')
        battle_id=opaque(battle.get('battle_id'))
        # A transient missing menu token is not a verified battle change. Keep
        # accepted healing streaks and observations until identity/end is known.
        ended=state.get('phase','world')=='world' and battle.get('active') is not True
        if not battle_id and not ended:return
        changed=False
        for key in ('intent','item_streak','pending'):
            value=self.data.get(key)
            if value and (ended or (battle_id and value.get('battle')!=battle_id)):
                self.data[key]=None;changed=True
        if changed:self._save()
        pending=self.data.get('pending')
        if not isinstance(pending,dict) or not identity:return
        # The raw server result can arrive before HP animations/events finish.
        terminal=battle.get('result_ready') is True or battle.get('can_advance') is True
        if not terminal and (not self._ready(state,battle) or identity[1]==pending.get('token')):return
        # The next controllable actor may differ. Attribute the observation to
        # the stored submitter, not to the current menu's actor.
        enemy=next((row for row in battle.get('fighters',[]) if isinstance(row,dict)
                    and row.get('group')==pending.get('enemy_group')
                    and row.get('form_id')==pending.get('enemy_form')),None)
        if pending.get('key') and enemy is not None and number(enemy.get('hp')):
            loss=max(0.,pending['enemy_hp']-float(enemy['hp']))
            collection='kill_bounds' if enemy['hp']==0 and loss>0 else 'samples'
            self._append_learning(collection,pending['key'],loss)
        actor=next((row for row in battle.get('fighters',[]) if isinstance(row,dict)
                    and row.get('group')==pending.get('actor_group')
                    and row.get('form_id')==pending.get('actor_form')),None)
        if actor is not None and number(actor.get('hp')) and number(pending.get('actor_hp')):
            loss=max(0.,pending['actor_hp']+pending.get('expected_heal',0)-actor['hp'])
            self._append_learning('incoming',self._key(pending['actor_form'],pending.get('enemy_form'),'incoming'),loss)
        self.data['pending']=None;self._save()

    def _reserve(self,battle,decision):
        identity=self._identity(battle)
        marker=opaque(':'.join(identity))
        if marker in self.data['handled']:return None
        decision={**decision,'expected_token':battle['menu_token'],'battle_id':battle['battle_id']}
        self.data['handled'].append(marker)
        self.data['decisions'].append({**self._safe_decision(decision),'submitted':False})
        self._save();return decision

    @staticmethod
    def _safe_decision(decision):
        keys=('option_index','target_group','kind','reason','skill_index','ds_cost','item_id','target_slot','back','enemy_hp','estimated_damage','estimated_turns','estimate_source','incoming_estimate','healing_estimate')
        result={key:decision[key] for key in keys if key in decision
                and (decision[key] is None or type(decision[key]) in (str,int,float,bool))}
        result['token_hash']=opaque(decision.get('expected_token'))
        result['battle_hash']=opaque(decision.get('battle_id'))
        return result

    def cancel(self,decision):
        """Release a reservation ONLY for a proven local pre-dispatch rejection.

        The caller must never use this after attempting RPC: acceptance could be
        ambiguous. Already-recorded accepted actions cannot be released here.
        """
        if not isinstance(decision,dict):return False
        identity=self._identity({'battle_id':decision.get('battle_id'),
                                 'menu_token':decision.get('expected_token')})
        if not identity:return False
        if any(row.get('submitted') is True and row.get('battle_hash')==identity[0]
               and row.get('token_hash')==identity[1] for row in self.data['decisions']):return False
        marker=opaque(':'.join(identity))
        if marker not in self.data['handled']:return False
        self.data['handled'].remove(marker);self._save();return True

    @staticmethod
    def _active_member(battle):
        actor=battle.get('actor') or {};party=battle.get('party',[])
        if type(actor.get('active_index')) is int:
            return next((member for member in party if isinstance(member,dict)
                         and member.get('slot')==actor['active_index']
                         and member.get('form_id')==actor.get('form_id')),None)
        matches=[member for member in party if isinstance(member,dict)
                 and member.get('form_id')==actor.get('form_id')]
        return matches[0] if len(matches)==1 else None

    def _incoming_estimate(self,battle):
        actor=battle.get('actor') or {};values=[]
        for enemy in self._enemies(battle):
            key=self._key(actor.get('form_id'),enemy.get('form_id'),'incoming')
            values.extend(v for v in self.learning['incoming'].get(key,[]) if number(v) and v>=0)
        return max(values) if values else None

    def _item_intent(self,battle,options):
        # Routine party HP and DS are handled after combat. A reserve's low HP
        # must not consume the active fighter's offensive turns.
        if not any(option.get('kind')=='items' for option in options):return None
        identity=self._identity(battle);streak=self.data.get('item_streak') or {}
        if streak.get('battle')==identity[0] and streak.get('count',0)>=1:return None
        actor=battle.get('actor') or {};member=self._active_member(battle)
        hp=actor.get('hp');maximum=actor.get('max_hp')
        if (not member or not number(hp) or not number(maximum) or hp<=0 or maximum<=0
                or member.get('hp')!=hp):return None
        incoming=self._incoming_estimate(battle)
        danger=hp<=maximum*.15 or (incoming is not None and incoming>0 and hp<=incoming*1.2)
        if not danger:return None
        heals=[]
        for item in battle.get('items',[]):
            if not isinstance(item,dict) or type(item_id(item)) is not int or not number(item.get('quantity')) or item['quantity']<=0:continue
            amount=self._heal_amount(item,'hp',maximum);gain=min(maximum-hp,amount)
            # Do not spend a turn on a heal that leaves us inside the same
            # observed danger range. One emergency item must then give way to
            # an accepted attack/skill before another item can be considered.
            required=incoming*1.2 if incoming is not None and incoming>0 else maximum*.15
            if gain>0 and hp+gain>required:
                heals.append((max(0,amount-(maximum-hp)),-gain,item_id(item)))
        if not heals:return None
        chosen=min(heals)[2]
        return {'item_id':chosen,'target_slot':member['slot'],'reason':'emergency_active_hp',
                'resource':'hp','incoming_estimate':incoming}

    @staticmethod
    def _heal_amount(item,kind,maximum):
        absolute=item.get('heal_'+kind,0);percent=item.get('heal_'+kind+'_percent',0)
        return ((max(0,absolute) if number(absolute) else 0)
                +maximum*(max(0,percent) if number(percent) else 0)/100)

    def _intent_useful(self,battle,intent):
        member=next((row for row in battle.get('party',[]) if isinstance(row,dict)
                     and row.get('slot')==intent.get('target_slot')),None)
        item=next((row for row in battle.get('items',[]) if isinstance(row,dict)
                   and item_id(row)==intent.get('item_id') and number(row.get('quantity'))
                   and row['quantity']>0),None)
        if member is None or item is None or not number(member.get('hp')) or member['hp']<=0:return False
        if intent.get('reason')!='emergency_active_hp' or intent.get('resource')!='hp':return False
        active=self._active_member(battle)
        if not active or active.get('slot')!=intent.get('target_slot'):return False
        resource='hp'
        maximum=member.get('max_'+resource);current=member.get(resource)
        return (number(maximum) and number(current) and 0<=current<maximum
                and self._heal_amount(item,resource,maximum)>0)

    def decide(self,state):
        self.observe(state)
        battle=battle_of(state);identity=self._identity(battle)
        if not identity or not self._ready(state,battle):return None
        if opaque(':'.join(identity)) in self.data['handled']:return None
        options=self._options(battle);menu=battle.get('menu');actor=battle.get('actor') or {}
        if menu!='main':
            if menu=='switch' and number(actor.get('hp')) and actor['hp']<=0:
                choices=[]
                for option in options:
                    if option.get('kind')!='switch_target' or type(option.get('target_slot')) is not int:continue
                    if option['target_slot']==actor.get('active_index'):continue
                    member=next((row for row in battle.get('party',[]) if isinstance(row,dict)
                                 and row.get('slot')==option['target_slot']),None)
                    if (member and number(member.get('hp')) and member['hp']>0
                            and number(member.get('max_hp')) and member['max_hp']>0):
                        choices.append((member['hp']/member['max_hp'],member['hp'],option))
                if not choices:return None
                choice=max(choices,key=lambda entry:entry[:2])[2]
                self.data['intent']=None
                return self._reserve(battle,{'option_index':choice['index'],'kind':'switch_target',
                    'target_slot':choice['target_slot'],'reason':'forced_switch_living_reserve'})
            intent=self.data.get('intent')
            if (isinstance(intent,dict) and intent.get('battle')==identity[0]
                    and self._intent_useful(battle,intent)):
                if menu=='items':
                    choice=next((option for option in options if option.get('kind')=='item'
                                 and option.get('item_id')==intent['item_id']),None)
                elif menu=='item_target' and battle.get('selected_item_id')==intent['item_id']:
                    choice=next((option for option in options if option.get('kind')=='item_target'
                                 and option.get('target_slot')==intent['target_slot']
                                 and option.get('item_id',intent['item_id'])==intent['item_id']),None)
                else:choice=None
                if choice is not None:
                    return self._reserve(battle,{'option_index':choice['index'],'kind':choice['kind'],
                        'item_id':intent['item_id'],'target_slot':intent['target_slot'],'reason':intent['reason']})
            self.data['intent']=None
            return self._reserve(battle,{'back':True,'kind':'back','reason':'unsupported_or_changed_submenu'})
        self.data['intent']=None
        offense=self._offense(battle,options)
        # A credible finishing command beats opening an item menu. A very weak
        # unknown target gets a free normal-attack probe, not DS exploration.
        if offense and offense.get('_finish_first'):
            offense.pop('_finish_first');return self._reserve(battle,offense)
        intent=self._item_intent(battle,options)
        if intent:
            self.data['intent']={**intent,'battle':identity[0]}
            choice=next(option for option in options if option.get('kind')=='items')
            return self._reserve(battle,{'option_index':choice['index'],'kind':'items',
                'target_slot':intent['target_slot'],'reason':intent['reason'],
                'incoming_estimate':intent['incoming_estimate']})
        if offense:
            offense.pop('_finish_first',None);return self._reserve(battle,offense)
        return None

    def _offense(self,battle,options):
        enemies=self._enemies(battle)
        if not enemies:return None
        actor=battle.get('actor') or {};actor_form=actor.get('form_id')
        attacks=[o for o in options if o.get('kind')=='attack']
        available_skills=[o for o in options if o.get('kind')=='skill' and type(o.get('skill_index')) is int
                and number(o.get('ds_cost')) and o['ds_cost']>=0 and number(actor.get('ds'))
                and number(actor.get('max_ds')) and actor['ds']>=o['ds_cost']]
        skills=[o for o in available_skills if actor['ds']-o['ds_cost']>=.1*actor['max_ds']]
        # Prefer an available normal-attack finisher, even if another target is
        # slightly weaker but has no observed basic-attack baseline.
        def basic_finisher(enemy):
            estimate=self._damage_estimate(self._key(actor_form,enemy.get('form_id'),'attack'))
            return estimate is not None and estimate>=enemy['hp']
        enemy=min(enemies,key=lambda e:(not basic_finisher(e),e['hp']))
        target=enemy['group'];hp=enemy['hp'];enemy_form=enemy.get('form_id')
        attack_estimate=self._damage_estimate(self._key(actor_form,enemy_form,'attack'))
        chosen=attacks[0] if attacks else None;estimate=attack_estimate;finish=False;reason='attack_fallback'
        known=[]
        for option in available_skills:
            damage=self._damage_estimate(self._key(actor_form,enemy_form,'skill',option['skill_index']))
            if damage is not None and damage>0:known.append((option,damage))
        if chosen is not None and attack_estimate is not None and attack_estimate>=hp:
            reason='observed_attack_sufficient';finish=True
        elif chosen is not None and attack_estimate is None and not (number(actor.get('hp')) and number(actor.get('max_hp'))
                and actor['hp']<=actor['max_hp']*.15 and any(damage>=hp for _,damage in known)):
            reason='attack_baseline_needed'
            if number(enemy.get('max_hp')) and hp<=max(1,enemy['max_hp']*.02):finish=True;reason='low_hp_attack_probe'
        else:
            finishers=[(option,damage) for option,damage in known if damage>=hp]
            if finishers:
                chosen,estimate=min(finishers,key=lambda row:(row[0]['ds_cost'],row[0]['skill_index']))
                reason='estimated_skill_finisher';finish=True
            else:
                attack_turns=math.ceil(hp/attack_estimate) if attack_estimate and attacks else math.inf
                useful=[(o,d) for o,d in known if o in skills and math.ceil(hp/d)<attack_turns]
                if useful:
                    chosen,estimate=min(useful,key=lambda row:(math.ceil(hp/row[1]),row[0]['ds_cost'],row[0]['skill_index']))
                    reason='estimated_skill_saves_turns'
                else:
                    untried=[o for o in skills if self._key(actor_form,enemy_form,'skill',o['skill_index']) not in self.data['explored']]
                    # Explore only after observing a normal-attack baseline,
                    # with substantial DS and a target requiring multiple hits.
                    if untried and (not attacks or (attack_estimate is not None and hp>attack_estimate*2
                            and actor.get('ds',0)>=actor.get('max_ds',0)*.35)):
                        chosen=min(untried,key=lambda o:(o['ds_cost'],o['skill_index']));estimate=None;reason='explore_unknown_skill'
        if chosen is None:return None
        decision={'option_index':chosen['index'],'target_group':target,'kind':chosen['kind'],'reason':reason,
                  'enemy_hp':hp,'estimated_damage':estimate,'_finish_first':finish}
        if chosen['kind']=='skill':decision.update(skill_index=chosen['skill_index'],ds_cost=chosen['ds_cost'])
        if estimate is not None and estimate>0:
            decision.update(estimated_turns=math.ceil(hp/estimate),estimate_source='conservative_observed_hp_loss_not_damage_guarantee')
        return decision

    def note_result(self,decision,before,after):
        """Record a bridge-accepted action; never infer acceptance from telemetry."""
        if not isinstance(decision,dict):return
        battle=battle_of(before);identity=self._identity(battle)
        if not identity or opaque(decision.get('expected_token'))!=identity[1]:return
        safe=self._safe_decision(decision);safe['submitted']=True
        self.data['decisions'].append(safe)
        kind=decision.get('kind')
        if kind in ('attack','skill'):self.data['item_streak']={'battle':identity[0],'count':0}
        if kind=='item_target':self.data['item_streak']={'battle':identity[0],'count':1}
        if kind in ('attack','skill','item_target'):
            actor=battle.get('actor') or {};enemies=self._enemies(battle)
            enemy=next((row for row in enemies if row['group']==decision.get('target_group')),None)
            if enemy is None and kind=='item_target':enemy=min(enemies,key=lambda row:row['hp'],default=None)
            if enemy is not None:
                if kind=='skill':self.data['explored'].append(self._key(actor.get('form_id'),enemy.get('form_id'),'skill',decision.get('skill_index')))
                heal=0
                if kind=='item_target' and decision.get('target_slot')==actor.get('active_index',0):
                    item=next((i for i in battle.get('items',[]) if item_id(i)==decision.get('item_id')),None)
                    if item:heal=min(actor.get('max_hp',0)-actor.get('hp',0),self._heal_amount(item,'hp',actor.get('max_hp',0)))
                self.data['pending']={'battle':identity[0],'token':identity[1],'actor_form':actor.get('form_id'),
                    'actor_group':actor.get('group'),'actor_hp':actor.get('hp'),'expected_heal':max(0,heal),
                    'enemy_group':enemy['group'],'enemy_form':enemy.get('form_id'),'enemy_hp':float(enemy['hp']),
                    'key':self._key(actor.get('form_id'),enemy.get('form_id'),kind,decision.get('skill_index')) if kind in ('attack','skill') else None}
        if kind=='item_target':self.data['intent']=None
        self._save()
