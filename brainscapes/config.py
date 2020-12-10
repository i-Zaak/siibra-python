# Copyright 2018-2020 Institute of Neuroscience and Medicine (INM-1), Forschungszentrum Jülich GmbH

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from os import path
from . import logger
from .commons import create_key
from .retrieval import cached_get

class ConfigurationRegistry:
    """
    Registers atlas configurations from json files managed in EBRAINS, by
    converting them to a specific object class based on the object construction
    function provided as constructor parameter. Used for atlas, space, and parcellation
    configurations. 

    This will be migrated to atlas ontology and openMINDS elememts from the KG in the future.
    """
    _ATLAS_CONFIG_CONTAINER_URL = 'https://object.cscs.ch/v1/AUTH_227176556f3c4bb38df9feea4b91200c/Brainscapes_Configuration/'

    def __init__(self,config_subfolder,cls):
        """
        Populate a new registry from the json files in the package path, using
        the "from_json" function of the provided class as hook function.
        """
        logger.debug("Initializing registry of type {} for {}".format(
            cls,config_subfolder))

        # Read atlas configurations from EBRAINS
        response = cached_get(self._ATLAS_CONFIG_CONTAINER_URL).decode()
        config_files = [ path for path in response.split() 
                if path.split('.')[-1] == "json"
                and path.startswith(config_subfolder) ]

        self.items = []
        self.by_key = {}
        self.by_id = {}
        self.by_name = {}
        self.cls = cls
        for configfile in config_files:
            url = self._ATLAS_CONFIG_CONTAINER_URL + configfile
            response = cached_get(url).decode()
            obj = json.loads(response, object_hook=cls.from_json)
            key = create_key(str(obj))
            identifier = obj.id
            logger.debug("Defining object '{}' with key '{}'".format( obj,key))
            self.items.append(obj)
            self.by_key[key] = len(self.items)-1
            self.by_id[identifier] = len(self.items)-1
            self.by_name[obj.name] = len(self.items)-1
        
    def load_config(self,config_file, object_hook):
        """
        Load a particular config file from EBRAINS
        """
        url = self._ATLAS_CONFIG_CONTAINER_URL + config_file
        response = cached_get(url).decode()
        return json.loads(response, object_hook=object_hook)

    def __getitem__(self,index):
        """
        Item access is implemented either by sequential index, key or id.
        """
        if isinstance(index,int) and index<len(self.items):
            return self.items[index]
        elif isinstance(index,self.cls) and (index in self.items):
            # index is itself already an object of this registry - forward
            return index
        elif index in self.by_key:
            return self.items[self.by_key[index]]
        elif index in self.by_id:
            return self.items[self.by_id[index]]
        elif index in self.by_name:
            return self.items[self.by_name[index]]
        else:
            raise ValueError("Cannot access this item in the {} Registry:".format(
                self.cls),index)

    def __dir__(self):
        return list(self.by_key.keys()) + list(self.by_id.keys())

    def __str__(self):
        return "\n".join([i.key for i in self.items])

    def __contains__(self,index):
        return index in self.__dir__()

    def __getattr__(self,name):
        if name in self.by_key.keys():
            return self.items[self.by_key[name]]
        else:
            raise AttributeError("No such attribute: {}".format(name))

