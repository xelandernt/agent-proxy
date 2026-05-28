from typing import Annotated

from fastapi import Depends

from proxy.settings import Config


def get_config() -> Config:
    from proxy.settings import CONFIG

    return CONFIG


ConfigDep = Annotated[Config, Depends(get_config)]
