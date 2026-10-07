import unittest
from collectors.permission_schemes import PermissionSchemesCollector
from collectors.notification_schemes import NotificationSchemesCollector
from collectors.governance_dependencies import GovernanceDependenciesCollector
class Fake:
 def __init__(self,g=None,p=None):self.g=g or {};self.p=p or {};self.calls=[]
 def get(self,e,params=None):return self.g.get(e)
 def get_paginated(self,e,values_key="values",params=None):return self.p.get(e,[])
 def get_optional(self,e,params=None,ignored_statuses=(404,)):self.calls.append(e);return self.g.get(e)
class Tests(unittest.TestCase):
 def test_permissions(self):
  payload={"permissionSchemes":[{"id":1,"name":"P","permissions":[{"id":2,"permission":"BROWSE_PROJECTS","holder":{"type":"projectRole","parameter":"10000"}}]}]};s,g=PermissionSchemesCollector(Fake(g={"/rest/api/3/permissionscheme":payload})).collect();self.assertEqual(s[0]["grantCount"],1);self.assertEqual(g[0]["holderType"],"projectRole")
 def test_notifications(self):
  data=[{"id":1,"name":"N","notificationSchemeEvents":[{"event":{"id":2,"name":"Issue Created"},"notifications":[{"id":3,"notificationType":"ProjectRole"}]}]}];s,e=NotificationSchemesCollector(Fake(p={"/rest/api/3/notificationscheme":data})).collect();self.assertEqual(e[0]["eventName"],"Issue Created")
 def test_archived_projects_skip_governance_requests(self):
  client=Fake(g={"/rest/api/3/project/ARC/permissionscheme":{"id":10}});p,n,s=GovernanceDependenciesCollector(client).collect([{"id":"1","key":"ARC","name":"A","archived":True}]);self.assertEqual((p,n,s),([],[],[]));self.assertEqual(client.calls,[])
 def test_active_project_governance_mappings(self):
  d={"/rest/api/3/project/ARC/permissionscheme":{"id":10},"/rest/api/3/project/ARC/notificationscheme":{"id":20},"/rest/api/3/project/ARC/issuesecuritylevelscheme":{"id":30}};p,n,s=GovernanceDependenciesCollector(Fake(g=d)).collect([{"id":"1","key":"ARC","name":"A","archived":False}]);self.assertEqual(p[0]["permissionSchemeId"],10);self.assertEqual(n[0]["notificationSchemeId"],20);self.assertEqual(s[0]["workItemSecuritySchemeId"],30)
if __name__=="__main__":unittest.main()
