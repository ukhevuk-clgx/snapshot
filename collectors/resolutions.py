from collectors.base import PaginatedCollector
class ResolutionsCollector(PaginatedCollector):
    entity_name='resolutions'
    endpoint='/rest/api/3/resolution/search'
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"isDefault":i.get("isDefault")}
