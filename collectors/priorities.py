from collectors.base import PaginatedCollector
class PrioritiesCollector(PaginatedCollector):
    entity_name='priorities'
    endpoint='/rest/api/3/priority/search'
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"statusColor":i.get("statusColor"),"isDefault":i.get("isDefault")}
