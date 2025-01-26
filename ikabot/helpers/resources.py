#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import math
from decimal import *

from ikabot.config import *

getcontext().prec = 30



def round_up_to_nearest(value, base=1000):
    """
    Arredonda o valor para cima, para o próximo múltiplo da base fornecida.
    Parameters
    ----------
    value : int
        O valor a ser arredondado.
    base : int
        O múltiplo de arredondamento (padrão: 100).
    Returns
    -------
    int
        O valor arredondado para cima.
    """
    return int(base * math.ceil(value / base))



def getAvailableResources(html, num=False):
    """
    Parameters
    ----------
    html : string

    Returns
    -------
    resources_available : list[int] | list[str]
    """
    resources = re.search(
        r'\\"resource\\":(\d+),\\"2\\":(\d+),\\"1\\":(\d+),\\"4\\":(\d+),\\"3\\":(\d+)}',
        html,
    )
    if num:
        return [
            int(resources.group(1)),
            int(resources.group(3)),
            int(resources.group(2)),
            int(resources.group(5)),
            int(resources.group(4)),
        ]
    else:
        return [
            resources.group(1),
            resources.group(3),
            resources.group(2),
            resources.group(5),
            resources.group(4),
        ]


def getWarehouseCapacity(html):
    """
    Parameters
    ----------
    html : string
    Returns
    -------
    capacity : int
    """
    capacity = re.search(
        r'maxResources:\s*JSON\.parse\(\'{\\"resource\\":(\d+),', html
    ).group(1)
    return int(capacity)


def getWineConsumptionPerHour(html):
    """
    Parameters
    ----------
    html : string
    Returns
    -------
    capacity : int
    """
    result = re.search(r"wineSpendings:\s(\d+)", html)
    if result:
        return int(result.group(1))
    return 0


def getProductionPerSecond(session, city_id):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    city_id : int

    Returns
    -------
    production: tuple[Decimal, Decimal, int]
    """
    prod = session.post(
        params={
            "action": "header",
            "function": "changeCurrentCity",
            "actionRequest": actionRequest,
            "cityId": city_id,
            "ajax": "1",
        }
    )
    prod = json.loads(prod, strict=False)
    prod = prod[0][1]["headerData"]
    wood_production = Decimal(prod["resourceProduction"])
    luxury_production = Decimal(prod["tradegoodProduction"])
    luxury_resource_type = int(prod["producedTradegood"])

    return wood_production, luxury_production, luxury_resource_type
