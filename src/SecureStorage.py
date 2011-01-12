# coding: utf-8

from google.appengine.ext.db import Model, TextProperty
import simplejson

class StorageModel(Model):
    data = TextProperty()
    
class SecureStorage:
    def __init__(self, key):
        self.key = key
        self.model = StorageModel.get_or_insert(key)
        if self.model.data == None:
            self.aData = {}
        else:
            self.aData = simplejson.loads(self.model.data)
    
    def get(self, name):
        return self.aData[name];
    
    def set(self, name, value):
        self.aData[name] = value;
        self.__save()
        
    def delete(self, name):
        del self.aData[name]
        self.__save()
    
    def getAll(self):
        return self.aData;

    def exist(self, name):
        return name in self.aData
    
    def __save(self):
        self.model.data = simplejson.dumps(self.aData)
        self.model.put()
        
    put = set
    
