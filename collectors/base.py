from abc import ABC,abstractmethod
from utils.logger import Logger
class BaseCollector(ABC):
    entity_name="items"
    def __init__(self,client):self.client=client
    def start(self):Logger.info(f"Collecting {self.entity_name}...")
    def done(self,rows):Logger.info(f"Collected {len(rows)} {self.entity_name}")
    @abstractmethod
    def collect(self):...
class PaginatedCollector(BaseCollector):
    endpoint=None;values_key="values";params=None
    def get_items(self):return self.client.get_paginated(self.endpoint,values_key=self.values_key,params=self.params) or []
    @abstractmethod
    def map_item(self,item):...
    def collect(self):self.start();rows=[self.map_item(x) for x in self.get_items()];self.done(rows);return rows
class ListCollector(BaseCollector):
    endpoint=None;params=None
    def get_items(self):
        p=self.client.get(self.endpoint,params=self.params) or []
        if not isinstance(p,list):raise TypeError(f"Expected list from {self.endpoint}")
        return p
    @abstractmethod
    def map_item(self,item):...
    def collect(self):self.start();rows=[self.map_item(x) for x in self.get_items()];self.done(rows);return rows
