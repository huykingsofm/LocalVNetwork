import sys

class CustomPrint(object):
    def __init__(self, name, configs, verbosities):
        # example_configs = {
        #   "user": {
        #       "notification",
        #       "warning",
        #       "error"
        #   },
        #   "dev": {
        #       "notification",
        #       "warning",
        #       "error",
        #       "debug"
        #   }
        # }
        self.__configs__ = configs
        
        self.__verbosities__ = verbosities

        for person in self.__verbosities__:
            if person not in self.__configs__:
                raise Exception("Allowed people {} must be in the config list".format(person))
            for level in self.__verbosities__[person]:
                if level not in self.__configs__[person]:
                    raise Exception("Allowed level {} must be in the config list".format(level))

        self.__name__ = name

    def __call__(self, people, level, *values, **kwargs):
        if people not in self.__configs__:
            raise Exception(f"Received people must be one of {list(self.__configs__.keys())}, rather than {people}")

        if level not in self.__configs__[people]:
            raise Exception(f"Level must be one of {self.__configs__[people]}, rather than {level}")

        if people not in self.__verbosities__:
            return
        
        if level not in self.__verbosities__[people]:
            return

        if self.__name__:
            print(f"{level} from {self.__name__}: ", *values, **kwargs)
        else:
            print(f"{level}: "*values, **kwargs)

    def use_dict(self, print_dict):
        for people in print_dict:
            for level in print_dict[people]:
                try:
                    self(people, level, print_dict[people][level])
                except:
                    continue

class StandardPrint(CustomPrint):
    def __init__(self, name, verbosities):
        super().__init__(
            name, 
            configs= {
                "user": {
                    "notification",
                    "warning",
                    "error"
                },
                "dev": {
                    "notification",
                    "warning",
                    "error",
                    "debug"
                }
            },
            verbosities= verbosities
        )

if __name__ == "__main__":
    __print__ = StandardPrint(
        "aa", 
        verbosities= {
            "user":{
                "notification"
            }
        }
    )
    __print__("dev", "warning", "huy", end = "1")