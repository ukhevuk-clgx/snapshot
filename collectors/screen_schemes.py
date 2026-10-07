from collectors.base import PaginatedCollector
class ScreenSchemesCollector(PaginatedCollector):
    entity_name='screen schemes'
    endpoint='/rest/api/3/screenscheme'
    params={'orderBy': 'name'}
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"defaultScreenId":(i.get("screens") or {}).get("default"),"createScreenId":(i.get("screens") or {}).get("create"),"editScreenId":(i.get("screens") or {}).get("edit"),"viewScreenId":(i.get("screens") or {}).get("view")}
