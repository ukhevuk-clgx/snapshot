from collectors.base import ListCollector
class ProjectRolesCollector(ListCollector):
    entity_name='project roles'
    endpoint='/rest/api/3/role'
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"actorCount":len(i.get("actors") or [])}
