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
                   'intent':None,'pending':None}
        self.learning={'version':1,'label':'Observed enemy HP loss; not a causal damage estimate',
                       'samples':{}}
        self._load(self.path,self.data)
        self._load(self.learning_path,self.learning)
        for key in ('handled','explored','decisions'):
            if not isinstance(self.data.get(key),list):self.data[key]=[]
            self.data[key]=self.data[key][-128:]
        if not isinstance(self.learning.get('samples'),dict):self.learning['samples']={}
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
        samples=self.learning['samples']
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

    def observe(self,state):
        battle=battle_of(state);identity=self._identity(battle);pending=self.data.get('pending')
        intent=self.data.get('intent')
        if intent and (not identity or intent.get('battle')!=identity[0]):self.data['intent']=None
        if not isinstance(pending,dict):return
        actor=battle.get('actor') or {}
        if (not identity or identity[0]!=pending.get('battle')
                or actor.get('form_id')!=pending.get('actor_form')):
            self.data['pending']=None;self._save();return
        if not self._ready(state,battle) or identity[1]==pending.get('token'):return
        enemy=next((row for row in battle.get('fighters',[]) if isinstance(row,dict)
                    and row.get('group')==pending.get('enemy_group')
                    and row.get('form_id')==pending.get('enemy_form')),None)
        if enemy is not None and number(enemy.get('hp')):
            loss=max(0.,pending['enemy_hp']-float(enemy['hp']))
            values=self.learning['samples'].setdefault(pending['key'],[])
            values.append(loss);self.learning['samples'][pending['key']]=values[-16:]
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
        keys=('option_index','target_group','kind','reason','skill_index','ds_cost','item_id','target_slot','back')
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

    def _item_intent(self,battle,options):
        actor=battle.get('actor') or {};party=battle.get('party') or []
        if not any(option.get('kind')=='items' for option in options):return None
        inventory=[item for item in battle.get('items',[]) if isinstance(item,dict)
                   and type(item_id(item)) is int and number(item.get('quantity')) and item['quantity']>0]
        heals=[]
        for member in party:
            if (not isinstance(member,dict) or type(member.get('slot')) is not int
                    or not number(member.get('hp')) or member['hp']<=0
                    or not number(member.get('max_hp')) or member['max_hp']<=0):continue
            if member['hp']/member['max_hp']<=.35:
                missing=member['max_hp']-member['hp']
                for item in inventory:
                    amount=self._heal_amount(item,'hp',member['max_hp'])
                    if amount>0:heals.append((member['hp']/member['max_hp'],-min(amount,missing),
                                              max(0,amount-missing),item_id(item),member['slot']))
        if heals:
            _,_,_,chosen,slot=min(heals)
            return {'item_id':chosen,'target_slot':slot,'reason':'low_hp_useful_item'}
        ds=actor.get('ds');maximum=actor.get('max_ds')
        if not number(ds) or not number(maximum) or maximum<=0 or ds>.2*maximum:return None
        # A low-DS skill row can be disabled by the original UI. Restoring DS
        # does not bypass that eligibility: the later skill decision still
        # requires an enabled row. Only its known cost informs recovery here.
        costs=[option['ds_cost'] for option in battle.get('options',[]) if isinstance(option,dict)
               and option.get('kind')=='skill' and number(option.get('ds_cost'))
               and 0<=option['ds_cost']<=.9*maximum]
        reserve=.1*maximum
        needed=[cost+reserve for cost in costs if ds<cost+reserve]
        member=self._active_member(battle)
        actor_slot=member.get('slot') if member and number(member.get('hp')) and member['hp']>0 else None
        if not needed or type(actor_slot) is not int:return None
        useful=[]
        for item in inventory:
            amount=self._heal_amount(item,'ds',maximum)
            if amount>0 and min(maximum,ds+amount)>=min(needed):
                useful.append((max(0,amount-(maximum-ds)),amount,item_id(item)))
        if not useful:return None
        return {'item_id':min(useful)[2],'target_slot':actor_slot,'reason':'low_ds_enables_skill'}

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
        resource='hp' if intent.get('reason')=='low_hp_useful_item' else 'ds'
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
        intent=self._item_intent(battle,options)
        if intent:
            self.data['intent']={**intent,'battle':identity[0]}
            choice=next(option for option in options if option.get('kind')=='items')
            return self._reserve(battle,{'option_index':choice['index'],'kind':'items','reason':intent['reason']})
        enemies=self._enemies(battle)
        if not enemies:return None
        enemy=min(enemies,key=lambda row:row['hp']);target=enemy['group']
        attacks=[option for option in options if option.get('kind')=='attack']
        actor_form=actor.get('form_id');enemy_form=enemy.get('form_id')
        attack_key=self._key(actor_form,enemy_form,'attack')
        attack_mean=self._mean(attack_key)
        skills=[]
        for option in options:
            if (option.get('kind')!='skill' or type(option.get('skill_index')) is not int
                    or not number(option.get('ds_cost')) or option['ds_cost']<0
                    or not number(actor.get('ds')) or not number(actor.get('max_ds'))):continue
            if actor['ds']-option['ds_cost']>=.1*actor['max_ds']:skills.append(option)
        reason='attack_fallback';chosen=attacks[0] if attacks else None
        if chosen is not None and attack_mean is not None and attack_mean>=enemy['hp']:
            reason='observed_attack_sufficient'
        else:
            untried=[option for option in skills if self._key(actor_form,enemy_form,'skill',option['skill_index'])
                     not in self.data['explored']]
            if untried:
                chosen=min(untried,key=lambda option:(option['ds_cost'],option['skill_index']))
                reason='explore_unknown_skill'
            elif attack_mean is not None or not attacks:
                ranked=[]
                for option in skills:
                    estimate=self._mean(self._key(actor_form,enemy_form,'skill',option['skill_index']))
                    if estimate is not None and estimate>0:
                        score=min(enemy['hp'],estimate)-option['ds_cost']*.5
                        if score>min(enemy['hp'],attack_mean or 0):ranked.append((score,-option['ds_cost'],option))
                if ranked:chosen=max(ranked,key=lambda row:row[:2])[2];reason='observed_skill_benefit_after_cost'
        if chosen is None:return None
        decision={'option_index':chosen['index'],'target_group':target,'kind':chosen['kind'],'reason':reason}
        if chosen['kind']=='skill':decision.update(skill_index=chosen['skill_index'],ds_cost=chosen['ds_cost'])
        if reason.startswith('observed_'):
            decision['estimate_source']='observed_enemy_hp_loss_not_causal_damage'
        return self._reserve(battle,decision)

    def note_result(self,decision,before,after):
        """Record a bridge-accepted action; never infer acceptance from telemetry."""
        if not isinstance(decision,dict):return
        battle=battle_of(before);identity=self._identity(battle)
        if not identity or opaque(decision.get('expected_token'))!=identity[1]:return
        safe=self._safe_decision(decision);safe['submitted']=True
        self.data['decisions'].append(safe)
        if decision.get('kind') in ('attack','skill'):
            actor=battle.get('actor') or {}
            enemy=next((row for row in self._enemies(battle) if row['group']==decision.get('target_group')),None)
            if enemy is not None:
                if decision['kind']=='skill':
                    self.data['explored'].append(self._key(actor.get('form_id'),enemy.get('form_id'),
                                                          'skill',decision.get('skill_index')))
                self.data['pending']={'battle':identity[0],'token':identity[1],
                    'actor_form':actor.get('form_id'),'enemy_group':enemy['group'],'enemy_form':enemy.get('form_id'),
                    'enemy_hp':float(enemy['hp']),'key':self._key(actor.get('form_id'),enemy.get('form_id'),
                                                              decision['kind'],decision.get('skill_index'))}
        if decision.get('kind')=='item_target':self.data['intent']=None
        self._save()
