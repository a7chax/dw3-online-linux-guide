"""Conservative HP/DS supplies policy; all effects require server confirmation."""
import json
import math
from pathlib import Path
import time
from inn_recovery import alignment
from shop_routes import ShopRoutes
from world_map import NoRouteError


def item_id(item):return item.get('item_id',item.get('id'))
def effect(item,kind):
    value=item.get('heal_'+kind,0)
    return value if type(value) is int and value>0 else 0

def stock(items,kind):return sum(max(0,i.get('quantity',0)) for i in items if effect(i,kind))
def quantity(items,wanted):return sum(max(0,i.get('quantity',0)) for i in items if item_id(i)==wanted)


class SuppliesRecovery:
    def __init__(self,session,*,router_factory=ShopRoutes,clock=time.time):
        self.path=Path(session)/'supplies-recovery.json';self.router_factory=router_factory;self.router=None;self.clock=clock
        try:saved=json.loads(self.path.read_text())
        except (OSError,ValueError):saved={}
        self.job=saved.get('job');self.use=saved.get('use');self.next_restock=saved.get('next_restock',0);self.inspected_pid=saved.get('inspected_pid');self.use_failures=saved.get('use_failures',[])[-32:];self.last_issue=saved.get('last_issue')

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps({'job':self.job,'use':self.use,'next_restock':self.next_restock,'inspected_pid':self.inspected_pid,'use_failures':self.use_failures[-32:],'last_issue':self.last_issue},indent=2)+'\n')
        tmp.chmod(0o600);tmp.replace(self.path)

    def report(self):return {'restocking':bool(self.job),'using_item':bool(self.use),'spent_bits':(self.job or {}).get('spent_bits',0),'last_issue':self.last_issue}
    @staticmethod
    def wait(reason):return {'action':None,'reason':reason}
    @staticmethod
    def closed(supplies):return not supplies.get('inventory_open') and not (supplies.get('shop') or {}).get('active')
    @staticmethod
    def close(supplies,reason):return {'action':'supplies_step','mode':'close','reason':reason,'expected_state_token':supplies['state_token']}

    def decide(self,state):
        if state.get('native_supplies_control') is not True:return None
        if any((state.get(k) or {}).get('active') for k in ('battle','story','inn')) or state.get('dialogue'):return None
        s=state.get('supplies') or {}
        if not s.get('state_token'):return None
        if s.get('telemetry_complete') is not True:
            if s.get('rules_loaded') is False and self.inspected_pid!=state.get('pid') and state.get('movement_ready') is True:
                return {'action':'supplies_step','mode':'inspect','reason':'load_item_rules_in_normal_inventory',
                        'pid':state['pid'],'expected_state_token':s['state_token']}
            return None
        party=s.get('party') or [];items=s.get('inventory') or [];shop=s.get('shop') or {}
        if not party or any(type(m.get(k)) is not int for m in party for k in ('slot','hp','max_hp','ds','max_ds')):return None
        if any(m['hp']==0 for m in party):return None
        if self.job and self.job.get('pid')!=state.get('pid'):self.job=None;self.save()
        if self.use and (self.use.get('pid')!=state.get('pid') or self.use.get('map')!=state.get('map')):self.use=None;self.save()
        if self.use:
            u=self.use;member=next((m for m in party if m['slot']==u['party_slot']),None)
            if not member:self.use=None;self.save();return None
            if u.get('submitted'):
                if quantity(items,u['item_id'])<u['before_quantity'] and (member['hp']>u['before_hp'] or member['ds']>u['before_ds']):
                    self.use=None;self.save()
                    if not self.closed(s):return self.close(s,'item_effect_confirmed')
                elif self.clock()-u['submitted_at']<20:return self.wait('item_use_verifying')
                else:
                    self.abandon_use('item_use_unconfirmed')
                    return self.close(s,'item_use_unconfirmed') if not self.closed(s) else None
            else:return self.use_decision(s)
        if self.job and self.job.get('pending'):
            p=self.job['pending'];bits=(state.get('wallet') or {}).get('bits')
            if (type(bits) is int and quantity(items,p['item_id'])>=p['before_quantity']+p['quantity']
                    and bits<=p['before_bits']-p['quantity']*p['unit_bits']):
                self.job['spent_bits']+=p['quantity']*p['unit_bits'];self.job['pending']=None;self.save()
            elif self.clock()-p['submitted_at']<20:return self.wait('purchase_verifying')
            else:
                self.last_issue='purchase_unconfirmed';self.job['pending']=None;self.job['complete']=True;self.save()
                return self.close(s,'purchase_unconfirmed')
        # Finish restocking before opening the inventory for world healing.
        if shop.get('active'):
            if self.job and self.job.get('complete'):return self.close(s,'restock_finished')
            return self.shop_decision(state,s,items,shop)
        if self.job and self.job.get('complete'):
            if not self.closed(s):return self.close(s,'restock_complete')
            self.job=None;self.next_restock=self.clock()+600;self.save()
        if not self.job:
            for kind,threshold in (('hp',.65),('ds',.25)):
                for member in sorted(party,key=lambda m:m[kind]/max(1,m['max_'+kind])):
                    maximum=member['max_'+kind];deficit=maximum-member[kind]
                    if maximum<=0 or member[kind]/maximum>threshold:continue
                    candidates=[i for i in items if i.get('quantity',0)>0 and effect(i,kind)>0
                                and self.use_identity(state['pid'],item_id(i),member,quantity(items,item_id(i))) not in self.use_failures]
                    if candidates:
                        chosen=min(candidates,key=lambda i:(max(0,effect(i,kind)-deficit),-min(deficit,effect(i,kind)),item_id(i)))
                        self.use={'pid':state['pid'],'map':state['map'],'item_id':item_id(chosen),'party_slot':member['slot'],
                                  'before_quantity':quantity(items,item_id(chosen)),'before_hp':member['hp'],'before_ds':member['ds']}
                        self.save();return self.use_decision(s)
            if not self.closed(s):return self.close(s,'supplies_menu_complete')
            if self.clock()<self.next_restock or all(stock(items,k)>=3 for k in ('hp','ds')):return None
            if not self.start_job(state):return None
        if state.get('movement_ready') is not True:return self.wait('supplies_waiting_for_world')
        nearby=[n for n in state.get('nearby_shops',[]) if n.get('map')==state['map']
                and f"{state['map']}:{n.get('entity_id')}" not in self.job.get('excluded_npcs',[])]
        npc=min(nearby,key=lambda n:(n.get('can_interact') is not True,math.dist((state['x'],state['y']),(n['x'],n['y']))),default=None)
        if npc:
            if npc.get('can_interact') or npc.get('interaction_facings'):
                facings=npc.get('interaction_facings') or [];step=alignment(state,npc)
                if facings and not npc.get('can_interact'):
                    face=min(facings,key=lambda f:min((f-state['facing'])%8,(state['facing']-f)%8))
                    step=(('down','down_left','left','up_left','up','up_right','right','down_right')[face],50)
                if not npc.get('can_interact') and step and self.job.get('align_attempts',0)<2:
                    return {'action':'supplies_align','reason':'face_item_merchant','step':step,'npc':npc,'map':state['map']}
                if self.job.get('interact_attempts',0)>=3:
                    self.job.setdefault('excluded_npcs',[]).append(f"{state['map']}:{npc.get('entity_id')}");self.save()
                    return self.wait('shop_interaction_unconfirmed')
                return {'action':'supplies_interact','reason':'speak_to_item_merchant','npc':npc,'map':state['map']}
            return {'action':'supplies_travel','reason':'approach_item_merchant','destination':(npc['x'],npc['y']),
                    'cross_map':False,'npc':npc,'map':state['map']}
        try:
            if self.router is None:self.router=self.router_factory()
            route=self.router.plan(state['map'],state['x'],state['y'],excluded=self.job.get('excluded',[]))
        except (OSError,ValueError,NoRouteError):
            self.job=None;self.next_restock=self.clock()+300;self.save();return None
        self.job['shop_id']=route['shop_id'];self.save();leg=route['legs'][0]
        if leg['kind']=='shop':return self.wait('shopkeeper_telemetry_unavailable')
        return {'action':'supplies_travel','reason':'travel_to_item_shop','destination':(leg['x'],leg['y']),
                'cross_map':leg['kind']=='exit','map':state['map'],'expected_next_maps':leg.get('expected_next_maps',[])}

    @staticmethod
    def use_identity(pid,wanted,member,count):
        return [pid,wanted,member['slot'],member['hp'],member['ds'],count]

    def abandon_use(self,reason):
        if self.use:
            u=self.use
            self.use_failures.append([u['pid'],u['item_id'],u['party_slot'],u['before_hp'],u['before_ds'],u['before_quantity']])
            self.use_failures=self.use_failures[-32:]
        self.use=None;self.last_issue=reason;self.save()

    def use_decision(self,s):
        return {'action':'supplies_step','mode':'use','reason':'restore_hp_or_ds','item_id':self.use['item_id'],
                'party_slot':self.use['party_slot'],'expected_state_token':s['state_token']}

    def start_job(self,state):
        wallet=state.get('wallet') or {};bits=wallet.get('bits')
        if wallet.get('telemetry_complete') is not True or type(bits) is not int or bits<=5000:return False
        budget=min(5000,bits//10,bits-5000)
        if budget<=0:return False
        self.job={'pid':state['pid'],'budget_bits':budget,'spent_bits':0,'reserve_bits':5000,
                  'excluded':[],'excluded_npcs':[],'failures':0,'align_attempts':0,'interact_attempts':0}
        self.save();return True

    def shop_decision(self,state,s,items,shop):
        if not self.job and not self.start_job(state):return self.close(s,'supplies_budget_unavailable')
        if shop.get('telemetry_complete') is not True:return self.wait('shop_telemetry_unavailable')
        if shop.get('submitting'):return self.wait('purchase_verifying')
        if shop.get('mode')!='buy':return self.close(s,'shop_not_in_buy_mode')
        wallet=state.get('wallet') or {};bits=wallet.get('bits')
        if wallet.get('telemetry_complete') is not True or type(bits) is not int:return self.wait('shop_wallet_unavailable')
        remaining=min(self.job['budget_bits']-self.job['spent_bits'],bits-self.job['reserve_bits'])
        for kind in ('hp','ds'):
            needed=max(0,3-stock(items,kind))
            if not needed:continue
            offers=[o for o in shop.get('offers',[]) if effect(o,kind)>0 and type(o.get('unit_bits')) is int
                    and 0<o['unit_bits']<=remaining and o.get('currency','bits')=='bits']
            if not offers:continue
            chosen=min(offers,key=lambda o:(o['unit_bits']/effect(o,kind),o['unit_bits'],item_id(o)))
            count=min(5,needed,remaining//chosen['unit_bits'],999-quantity(items,item_id(chosen)))
            if count<1:continue
            return {'action':'supplies_step','mode':'buy','reason':'restock_'+kind,'item_id':item_id(chosen),'quantity':count,
                    'unit_bits':chosen['unit_bits'],'expected_offer_token':shop['offer_token'],'expected_state_token':s['state_token'],
                    'before_quantity':quantity(items,item_id(chosen)),'before_bits':bits,'reserve_bits':self.job['reserve_bits'],
                    'max_total_bits':remaining}
        self.job['complete']=True;self.save();return self.close(s,'restock_complete_or_unavailable')

    def note_result(self,decision,result):
        plan=result.get('plan') or {};action=decision['action']
        if action=='supplies_step' and decision['mode']=='inspect' and plan.get('key')=='i':
            self.inspected_pid=decision['pid']
        if action=='supplies_step' and not plan.get('key'):
            if decision['mode']=='use':self.abandon_use(plan.get('reason','item_use_unavailable'))
            elif decision['mode']=='buy' and self.job:
                self.last_issue=plan.get('reason','purchase_unavailable');self.job['complete']=True
        if action=='supplies_step' and plan.get('submit'):
            if decision['mode']=='use' and self.use:
                self.use.update(submitted=True,submitted_at=self.clock())
            elif decision['mode']=='buy' and self.job:
                self.job['pending']={k:decision[k] for k in ('item_id','quantity','unit_bits','before_quantity','before_bits')}
                self.job['pending']['submitted_at']=self.clock()
        elif self.job:
            if action=='supplies_align':self.job['align_attempts']+=1
            elif action=='supplies_interact':self.job['interact_attempts']+=1
            elif action=='supplies_travel':
                if result.get('reason')=='map_changed':self.job.update(align_attempts=0,interact_attempts=0,failures=0)
                elif result.get('reason') in ('unable_to_advance','no_map_exit_detected','local_route_unavailable'):
                    self.job['failures']+=1
                    if self.job['failures']>=3:
                        self.job.setdefault('excluded',[]).append(self.job.get('shop_id'));self.job['failures']=0
        self.save()
