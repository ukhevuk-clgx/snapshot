from collectors.base import BaseCollector
class FieldConfigurationSchemesCollector(BaseCollector):
 entity_name="field configuration schemes"
 def collect(self):
  self.start();schemes=[{"id":x.get("id"),"name":x.get("name"),"description":x.get("description")} for x in self.client.get_paginated("/rest/api/3/fieldconfigurationscheme")];maps=[{"fieldConfigurationSchemeId":x.get("fieldConfigurationSchemeId"),"issueTypeId":x.get("issueTypeId"),"fieldConfigurationId":x.get("fieldConfigurationId")} for x in self.client.get_paginated("/rest/api/3/fieldconfigurationscheme/mapping")];counts={}
  for x in maps:counts[x["fieldConfigurationSchemeId"]]=counts.get(x["fieldConfigurationSchemeId"],0)+1
  for x in schemes:x["mappingCount"]=counts.get(x["id"],0)
  self.done(schemes);return schemes,maps
