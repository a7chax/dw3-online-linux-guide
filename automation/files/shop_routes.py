"""Item-shop routes from the same collision-checked hints used for inns."""
from inn_routes import InnRoutes
from world_map import ATLAS

class ShopRoutes(InnRoutes):
    def __init__(self,root=ATLAS):
        super().__init__(root,npc_id=22,poi_type=0,sprite='p038wiza')

    def is_shop_dialogue(self,map_id,dialogue):
        return self.is_inn_dialogue(map_id,dialogue)

    def plan(self,map_id,x,y,excluded=()):
        result=super().plan(map_id,x,y,excluded=excluded)
        result['shop_id']=result.pop('inn_id')
        for leg in result['legs']:
            leg['kind']={'inn':'shop','inn_approach':'shop_approach'}.get(leg['kind'],leg['kind'])
            if 'innmap' in leg:leg['shopmap']=leg.pop('innmap')
        return result
