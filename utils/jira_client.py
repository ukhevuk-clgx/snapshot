import random,time,requests
from threading import Lock,local
from config import *
from utils.logger import Logger
class JiraClient:
    RETRYABLE={429,500,502,503,504}
    def __init__(self):
        self.site=SITE.rstrip("/")
        self._local=local();self._sessions=[];self._sessions_lock=Lock()
        self.session=self._get_session()
    def _get_session(self):
        if not hasattr(self._local,"session"):
            session=requests.Session()
            session.auth=(EMAIL,TOKEN)
            session.headers.update({"Accept":"application/json","User-Agent":"JiraSnapshot/5.0"})
            self._local.session=session
            with self._sessions_lock:self._sessions.append(session)
        return self._local.session
    def __enter__(self):return self
    def __exit__(self,*a):
        for session in self._sessions:session.close()
    def get(self,endpoint,params=None):
        url=endpoint if endpoint.startswith("http") else self.site+endpoint
        for attempt in range(1,MAX_RETRY_ATTEMPTS+1):
            try:
                r=self._get_session().get(url,params=params,timeout=REQUEST_TIMEOUT)
                if r.status_code in self.RETRYABLE and attempt<MAX_RETRY_ATTEMPTS:
                    d=float(r.headers.get("Retry-After",min(2**(attempt-1),30)+random.random()));Logger.warning(f"GET {r.url} returned {r.status_code}; retrying in {d:.1f}s");time.sleep(d);continue
                r.raise_for_status();return None if r.status_code==204 or not r.content else r.json()
            except (requests.Timeout,requests.ConnectionError):
                if attempt==MAX_RETRY_ATTEMPTS:raise
                time.sleep(min(2**(attempt-1),30)+random.random())
        raise RuntimeError(f"GET failed: {url}")
    def get_optional(self,endpoint,params=None,ignored_statuses=(404,)):
        try:return self.get(endpoint,params)
        except requests.HTTPError as exc:
            status=exc.response.status_code if exc.response is not None else None
            if status in ignored_statuses:Logger.warning(f"Skipping optional endpoint {endpoint}: HTTP {status}");return None
            raise
    def get_paginated(self,endpoint,values_key="values",params=None,page_size=DEFAULT_PAGE_SIZE):
        out=[];start=0;base=dict(params or {})
        while True:
            p=self.get(endpoint,{**base,"startAt":start,"maxResults":page_size})
            if isinstance(p,list):out.extend(p);break
            if not isinstance(p,dict):raise TypeError(f"Unexpected response from {endpoint}")
            batch=p.get(values_key,[])
            if not isinstance(batch,list):raise TypeError(f"Expected {values_key} list from {endpoint}")
            out.extend(batch);n=len(batch);total=p.get("total")
            if p.get("isLast") is True or n==0 or (total is not None and len(out)>=int(total)) or (total is None and p.get("isLast") is None and n<page_size):break
            nxt=p.get("startAt",start)+n
            if nxt<=start:raise RuntimeError(f"Pagination did not advance for {endpoint}")
            start=nxt
        return out
    def test_connection(self):
        Logger.info("Testing Jira connection");u=self.get("/rest/api/3/myself");Logger.info(f"Connected successfully as '{u.get('displayName','Unknown User')}'");return u
