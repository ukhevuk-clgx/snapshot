from collectors.base import PaginatedCollector
class ProjectsCollector(PaginatedCollector):
    entity_name='projects'
    endpoint='/rest/api/3/project/search'
    params={'orderBy': 'key', 'status': ['live', 'archived']}
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"key":i.get("key"),"projectTypeKey":i.get("projectTypeKey"),"simplified":i.get("simplified"),"archived":i.get("archived")}
