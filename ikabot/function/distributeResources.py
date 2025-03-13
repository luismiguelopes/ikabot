#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import traceback
import math
import random
import time

from ikabot.config import *
from ikabot.helpers.botComm import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import banner
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.planRoutes import executeRoutes
from ikabot.helpers.process import set_child_mode
from ikabot.helpers.resources import *
from ikabot.helpers.signals import setInfoSignal
from ikabot.helpers.varios import addThousandSeparator

def distributeResources(session, event, stdin_fd, predetermined_input):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    event : multiprocessing.Event
    stdin_fd: int
    predetermined_input : multiprocessing.managers.SyncManager.list
    """
    sys.stdin = os.fdopen(stdin_fd)
    config.predetermined_input = predetermined_input
    try:
        banner()

        print("What type of ships do you want to use? (Default: Trade ships)")
        print("(1) Trade ships")
        print("(2) Freighters")
        shiptype = read(min=1, max=2, digit=True, empty=True)
        if shiptype == '':
            shiptype = 1
        if shiptype == 1:
            useFreighters = False
        elif shiptype == 2:
            useFreighters = True

        print("What resource do you want to distribute?")
        print("(0) Exit")
        for i in range(len(materials_names)):
            print("({:d}) {}".format(i + 1, materials_names[i]))
        resource = read(min=0, max=5)
        if resource == 0:
            event.set()  # give main process control before exiting
            return
        resource -= 1

        print("\nHow do you want to distribute the resources?")
        print("1) From cities that produce them to cities that do not")
        print("2) Distribute them evenly among all cities")
        print("3) Combine 1 and 2 (from producers to non-producers, evenly)")
        type_distribution = read(min=1, max=3)
        evenly = type_distribution == 2
        combined = type_distribution == 3

        (cities_ids, cities) = getIdsOfCities(session)
        choice = None
        ignored_cities = []
        while True:
            banner()
            displayed_string = (
                f'(currently ignoring: {", ".join(ignored_cities)})'
                if ignored_cities
                else ""
            )
            print(f"Select cities to ignore. {displayed_string}")
            print("0) Continue")
            choice_to_cityid_map = []
            for i, city in enumerate(cities.values()):
                choice_to_cityid_map.append(city["id"])
                print(f'{i + 1}) {city["name"]} - {materials_names[city["tradegood"]]}')
            choice = read(min=0, max=len(cities_ids))
            if choice == 0:
                break
            city_id = choice_to_cityid_map[choice - 1]
            cities_ids = list(filter(lambda x: x != str(city_id), cities_ids))
            ignored_cities.append(cities[str(city_id)]["name"])
            del cities[str(city_id)]

        if evenly:
            routes = distribute_evenly(session, resource, cities_ids, cities)
        elif combined:
            routes = distribute_combined(session, resource, cities_ids, cities)
        else:
            routes = distribute_unevenly(session, resource, cities_ids, cities)

        if routes is None:
            event.set()
            return

        banner()
        print("\nThe following shipments will be made:\n")
        for route in routes:
            print(
                "{} -> {} : {} {}".format(
                    route[0]["name"],
                    route[1]["name"],
                    route[resource + 3],
                    materials_names[resource],
                )
            )
        print("\nProceed? [Y/n]")
        rta = read(values=["y", "Y", "n", "N", ""])
        if rta.lower() == "n":
            event.set()
            return

    except KeyboardInterrupt:
        event.set()
        return

    set_child_mode(session)
    event.set()  # this is where we give back control to main process

    info = "\nDistribute {}\n".format(materials_names[resource])
    setInfoSignal(session, info)

    try:
        executeRoutes(session, routes, useFreighters)  # plan trips for all the routes
    except Exception as e:
        msg = "Error in:\n{}\nCause:\n{}".format(info, traceback.format_exc())
        sendToBot(session, msg)  # sends message to telegram bot
    finally:
        session.logout()

def distribute_evenly(session, resource_type, cities_ids, cities):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    resource_type : int
    """
    resourceTotal = 0

    originCities = {}
    destinationCities = {}
    allCities = {}
    for cityID in cities_ids:

        html = session.get(city_url + cityID)
        city = getCity(html)

        resourceTotal += city["availableResources"][resource_type]
        allCities[cityID] = city

    # Calculate the average resources per city, ignoring cities that need less than 5000
    resourceAverage = round_to_nearest(resourceTotal // len(allCities))
    while True:
        len_prev = len(destinationCities)
        for cityID in allCities:
            if cityID in destinationCities:
                continue
            freeStorage = allCities[cityID]["freeSpaceForResources"][resource_type]
            storage = allCities[cityID]["storageCapacity"]
            if storage < resourceAverage or freeStorage < 5000:
                destinationCities[cityID] = freeStorage
                resourceTotal -= storage

        resourceAverage = resourceTotal // (len(allCities) - len(destinationCities))

        if len_prev == len(destinationCities):
            for cityID in allCities:
                if cityID in destinationCities:
                    continue
                if allCities[cityID]["availableResources"][resource_type] > resourceAverage:
                    originCities[cityID] = allCities[cityID]["availableResources"][resource_type] - resourceAverage
                else:
                    destinationCities[cityID] = resourceAverage - allCities[cityID]["availableResources"][resource_type]
            break

    originCities = {k: v for k, v in sorted(originCities.items(), key=lambda item: item[1], reverse=True)}
    destinationCities = {k: v for k, v in sorted(destinationCities.items(), key=lambda item: item[1])}

    routes = []

    for originCityID in originCities:
        for destinationCityID in destinationCities:
            if originCities[originCityID] == 0 or destinationCities[destinationCityID] == 0:
                continue

            if originCities[originCityID] > destinationCities[destinationCityID]:
                toSend = round_to_nearest(destinationCities[destinationCityID])
            else:
                toSend = originCities[originCityID]

            if toSend == 0:
                continue

            toSendArr = [0] * len(materials_names)
            toSendArr[resource_type] = toSend
            route = (allCities[originCityID], allCities[destinationCityID], allCities[destinationCityID]["islandId"], *toSendArr)
            routes.append(route)

            if originCities[originCityID] > destinationCities[destinationCityID]:
                originCities[originCityID] -= destinationCities[destinationCityID]
                destinationCities[destinationCityID] = 0
            else:
                destinationCities[destinationCityID] -= originCities[originCityID]
                originCities[originCityID] = 0

    return routes

def distribute_unevenly(session, resource_type, cities_ids, cities):
    """
    Parameters
    ----------
    session : ikabot.web.session.Session
    resource_type : int
    """
    total_available_resources_from_all_cities = 0
    origin_cities = {}
    destination_cities = {}

    # First, identify origin and destination cities
    for destination_city_id in cities_ids:
        is_city_mining_this_resource = (
            cities[destination_city_id]["tradegood"] == resource_type
        )
        if is_city_mining_this_resource:
            html = session.get(city_url + destination_city_id)
            city = getCity(html)
            if resource_type == 1:  # wine
                city["available_amount_of_resource"] = (
                    city["availableResources"][resource_type]
                    - city["wineConsumptionPerHour"]
                    - 1
                )
            else:
                city["available_amount_of_resource"] = city["availableResources"][
                    resource_type
                ]
            if city["available_amount_of_resource"] < 0:
                city["available_amount_of_resource"] = 0
            total_available_resources_from_all_cities += city[
                "available_amount_of_resource"
            ]
            origin_cities[destination_city_id] = city
        else:
            html = session.get(city_url + destination_city_id)
            city = getCity(html)
            city["free_storage_for_resource"] = city["freeSpaceForResources"][
                resource_type
            ]
            # Ignore cities that need less than 5000 resources
            if city["free_storage_for_resource"] >= 5000:
                destination_cities[destination_city_id] = city

    # Check if there are resources to send or cities to send to
    if total_available_resources_from_all_cities <= 0:
        print("\nThere are no resources to send.")
        enter()
        return None
    if len(destination_cities) == 0:
        print("\nThere is no space available to send resources.")
        enter()
        return None

    # Calculate the amount of resources to send to each city
    remaining_resources_to_be_sent_to_each_city = round_to_nearest(
        total_available_resources_from_all_cities // len(destination_cities)
    )
    free_storage_available_per_city = [
        destination_cities[city]["free_storage_for_resource"]
        for city in destination_cities
    ]
    total_free_storage_available_in_all_cities = sum(free_storage_available_per_city)
    remaining_resources_to_send = min(
        total_available_resources_from_all_cities,
        total_free_storage_available_in_all_cities,
    )
    toSend = {}

    # Distribute resources, ensuring no city gets less than 5000
    while remaining_resources_to_send > 0:
        len_prev = len(toSend)
        for city_id in destination_cities:
            city = destination_cities[city_id]
            if (
                city_id not in toSend
                and city["free_storage_for_resource"]
                < remaining_resources_to_be_sent_to_each_city
            ):
                toSend[city_id] = city["free_storage_for_resource"]
                remaining_resources_to_send -= city["free_storage_for_resource"]

        if len(toSend) == len_prev:
            for city_id in destination_cities:
                if city_id not in toSend:
                    toSend[city_id] = remaining_resources_to_be_sent_to_each_city
            break

        free_storage_available_per_city = [
            destination_cities[city]["free_storage_for_resource"]
            for city in destination_cities
            if city not in toSend
        ]
        if len(free_storage_available_per_city) == 0:
            break
        total_free_storage_available_in_all_cities = sum(
            free_storage_available_per_city
        )
        remaining_resources_to_send = min(
            remaining_resources_to_send, total_free_storage_available_in_all_cities
        )
        remaining_resources_to_be_sent_to_each_city = (
            remaining_resources_to_send // len(free_storage_available_per_city)
        )

    # Create routes for sending resources
    routes = []
    for destination_city_id in destination_cities:
        destination_city = destination_cities[destination_city_id]
        island_id = destination_city["islandId"]
        missing_resources = toSend[destination_city_id]
        for origin_city_id in origin_cities:
            if missing_resources == 0:
                break

            origin_city = origin_cities[origin_city_id]
            resources_available_in_this_city = origin_city[
                "available_amount_of_resource"
            ]
            for route in routes:
                origin = route[0]
                resource = route[resource_type + 3]
                if origin["id"] == origin_city_id:
                    resources_available_in_this_city -= resource

            send_this_round = min(
                round_to_nearest(missing_resources),
                round_to_nearest(resources_available_in_this_city),
            )
            available = destination_city["free_storage_for_resource"]
            if available == 0 or send_this_round == 0:
                continue

            if available < send_this_round:
                missing_resources = 0
                send_this_round = available
            else:
                missing_resources -= send_this_round

            toSendArr = [0] * len(materials_names)
            toSendArr[resource_type] = send_this_round
            route = (origin_city, destination_city, island_id, *toSendArr)
            routes.append(route)

    return routes

def distribute_combined(session, resource_type, cities_ids, cities):
    """
    Distribui recursos de forma que todas as cidades de destino terminem com a mesma quantidade,
    considerando os recursos já existentes e o espaço livre, e corrigindo o problema de exceder
    os recursos disponíveis na cidade de origem.  Adiciona pausa aleatória entre transportes.
    """
    total_available_resources = 0
    origin_cities = {}
    destination_cities = {}

    # Identifica cidades de origem e destino
    for city_id in cities_ids:
        city = cities[city_id]
        if city["tradegood"] == resource_type:
            # Cidade produtora
            html = session.get(city_url + city_id)
            city = getCity(html)

            if resource_type == 1:  # vinho
                city["available_amount_of_resource"] = (
                    city["availableResources"][resource_type]
                    - city["wineConsumptionPerHour"]
                    - 1
                )
                city["available_amount_of_resource"] = max(0, city["available_amount_of_resource"])
            else:
                city["available_amount_of_resource"] = city["availableResources"][resource_type]

            total_available_resources += city["available_amount_of_resource"]
            origin_cities[city_id] = city
        else:
            # Cidade não produtora
            html = session.get(city_url + city_id)
            city = getCity(html)

            city["free_storage_for_resource"] = city["freeSpaceForResources"][resource_type]

            if city["free_storage_for_resource"] >= 1000:  # Limiar
                destination_cities[city_id] = city

    if total_available_resources <= 0:
        return None
    if len(destination_cities) == 0:
        return None

    # 1. Calcular a Quantidade Total Necessária
    total_resources_needed = sum(city["availableResources"][resource_type] for city in destination_cities.values())

    # 2. Calcular a Média Desejada (incluindo os recursos da cidade de origem)
    total_resources_available = total_available_resources + total_resources_needed
    average_resources_per_city = total_resources_available // len(destination_cities)

    routes = []
    consolidated_routes = {}

    for destination_city_id in destination_cities:
        destination_city = destination_cities[destination_city_id]

        if destination_city_id not in consolidated_routes:
            consolidated_routes[destination_city_id] = {
                "destination": destination_city,
                "total_resources": 0,
                "origin_cities": []
            }

        # 3. Calcular a Quantidade a Enviar
        amount_to_send = average_resources_per_city - destination_city["availableResources"][resource_type]

        # Arredondar para baixo para o múltiplo de 1000 mais próximo
        amount_to_send = (amount_to_send // 1000) * 1000

        if amount_to_send < 1000:  # Limiar
            continue

        missing_resources = amount_to_send

        for origin_city_id in origin_cities:
            if missing_resources == 0:
                break

            origin_city = origin_cities[origin_city_id]
            resources_available = origin_city["available_amount_of_resource"]

            # ***VERIFICAÇÃO IMPORTANTE***
            total_sent_from_origin = sum(
                sent
                for dest_id, data in consolidated_routes.items()
                if dest_id != destination_city_id
                for origin, sent in data["origin_cities"]
                if origin["id"] == origin_city_id
            )

            if resources_available - total_sent_from_origin <= 0:
                continue

            send_this_round = min(missing_resources, resources_available - total_sent_from_origin)

            if send_this_round < 1000:
                continue

            consolidated_routes[destination_city_id]["total_resources"] += send_this_round
            consolidated_routes[destination_city_id]["origin_cities"].append((origin_city, send_this_round))

            origin_city["available_amount_of_resource"] -= send_this_round
            missing_resources -= send_this_round

    for destination_city_id, data in consolidated_routes.items():
        destination_city = data["destination"]
        total_resources = data["total_resources"]
        origin_cities_list = data["origin_cities"]

        if origin_cities_list:
            toSendArr = [0] * len(materials_names)
            toSendArr[resource_type] = total_resources
            route = (origin_cities_list[0][0], destination_city, destination_city["islandId"], *toSendArr)
            routes.append(route)

    return routes