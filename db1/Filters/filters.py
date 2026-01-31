from fastapi_filter.contrib.sqlalchemy import Filter
from typing import Optional
from db1.models.Base1 import User,Project,Task


class UserFilter(Filter):
    username__ilike:Optional[str]=None
    email__ilike:Optional[str]=None
    class Constants(Filter.Constants):
       model=User
class ProjectFilter(Filter):
    title__ilike:Optional[str]=None
    owner_id__eq:Optional[int]=None
    class Constants(Filter.Constants):
        model=Project

class TaskFilter(Filter):
    title__ilike:Optional[str]=None
    class Constants(Filter.Constants):
        model=Task
