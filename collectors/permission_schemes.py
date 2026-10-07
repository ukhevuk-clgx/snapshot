from collectors.base import BaseCollector
class PermissionSchemesCollector(BaseCollector):
 entity_name="permission schemes"
 def collect(self):
  self.start();payload=self.client.get("/rest/api/3/permissionscheme",params={"expand":"permissions"}) or {};rows=[];grants=[]
  for s in payload.get("permissionSchemes",[]):
   ps=s.get("permissions") or [];rows.append({"id":s.get("id"),"name":s.get("name"),"description":s.get("description"),"grantCount":len(ps)})
   for g in ps:
    h=g.get("holder") or {};grants.append({"permissionSchemeId":s.get("id"),"permissionSchemeName":s.get("name"),"grantId":g.get("id"),"permission":g.get("permission"),"holderType":h.get("type"),"holderParameter":h.get("parameter"),"holderValue":h.get("value")})
  self.done(rows);return rows,grants
