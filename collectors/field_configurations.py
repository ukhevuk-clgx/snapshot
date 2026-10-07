from collectors.base import PaginatedCollector
class FieldConfigurationsCollector(PaginatedCollector):
    entity_name='field configurations'
    endpoint='/rest/api/3/fieldconfiguration'
    def map_item(self,i):return {"id":i.get("id"),"name":i.get("name"),"description":i.get("description"),"isDefault":i.get("isDefault")}
