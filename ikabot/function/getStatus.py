#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json  # Importar o módulo json
from decimal import *

from ikabot.config import *
from ikabot.helpers.getJson import getCity
from ikabot.helpers.gui import *
from ikabot.helpers.market import getGold
from ikabot.helpers.naval import *
from ikabot.helpers.pedirInfo import *
from ikabot.helpers.resources import *
from ikabot.helpers.varios import *

getcontext().prec = 30

def getStatus(session, event, stdin_fd, predetermined_input):
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
        color_arr = [
            bcolors.ENDC,
            bcolors.HEADER,
            bcolors.STONE,
            bcolors.BLUE,
            bcolors.WARNING,
        ]

        (ids, cities) = getIdsOfCities(session)
        total_resources = [0] * len(materials_names)
        total_production = [0] * len(materials_names)
        total_wine_consumption = 0
        housing_space = 0
        citizens = 0
        total_housing_space = 0
        total_citizens = 0
        available_ships = 0
        total_ships = 0
        for id in ids:
            session.get("view=city&cityId={}".format(id), noIndex=True)
            data = session.get("view=updateGlobalData&ajax=1", noIndex=True)
            json_data = json.loads(data, strict=False)
            json_data = json_data[0][1]["headerData"]
            if json_data["relatedCity"]["owncity"] != 1:
                continue
            wood = Decimal(json_data["resourceProduction"])
            good = Decimal(json_data["tradegoodProduction"])
            typeGood = int(json_data["producedTradegood"])
            total_production[0] += wood * 3600
            total_production[typeGood] += good * 3600
            total_wine_consumption += json_data["wineSpendings"]
            housing_space = int(json_data["currentResources"]["population"])
            citizens = int(json_data["currentResources"]["citizens"])
            total_housing_space += housing_space
            total_citizens += citizens
            total_resources[0] += json_data["currentResources"]["resource"]
            total_resources[1] += json_data["currentResources"]["1"]
            total_resources[2] += json_data["currentResources"]["2"]
            total_resources[3] += json_data["currentResources"]["3"]
            total_resources[4] += json_data["currentResources"]["4"]
            available_ships = json_data["freeTransporters"]
            total_ships = json_data["maxTransporters"]
            total_gold = int(Decimal(json_data["gold"]))
            total_gold_production = int(
                Decimal(
                    json_data["scientistsUpkeep"]
                    + json_data["income"]
                    + json_data["upkeep"]
                )
            )

        # Criando um dicionário com os dados resumidos
        status_summary = {
            "ships": {
                "available": int(available_ships),
                "total": int(total_ships)
            },
            "resources": {
                "available": [int(resource) for resource in total_resources],  # Convertendo Decimal para int
                "production": [int(production) for production in total_production]  # Convertendo Decimal para int
            },
            "housing": {
                "space": int(total_housing_space),
                "citizens": int(total_citizens)
            },
            "gold": {
                "total": int(total_gold),
                "production": int(total_gold_production)
            },
            "wine_consumption": int(total_wine_consumption)  # Convertendo Decimal para int
        }

        # Salvando o dicionário em um arquivo JSON
        logs_dir = "/tmp/ikalogs/"
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        
        with open(os.path.join(logs_dir, "statusSummary.json"), "w") as json_file:
            json.dump(status_summary, json_file, indent=4)

        print("Ships {:d}/{:d}".format(int(available_ships), int(total_ships)))
        print("\nTotal:")
        print("{:>10}".format(" "), end="|")
        for i in range(len(materials_names)):
            print("{:>12}".format(materials_names_english[i]), end="|")
        print()
        print("{:>10}".format("Available"), end="|")
        for i in range(len(materials_names)):
            print("{:>12}".format(addThousandSeparator(total_resources[i])), end="|")
        print()
        print("{:>10}".format("Production"), end="|")
        for i in range(len(materials_names)):
            print("{:>12}".format(addThousandSeparator(total_production[i])), end="|")
        print()
        print(
            "Housing Space: {}, Citizens: {}".format(
                addThousandSeparator(total_housing_space),
                addThousandSeparator(citizens),
            )
        )
        print(
            "Gold: {}, Gold production: {}".format(
                addThousandSeparator(total_gold),
                addThousandSeparator(total_gold_production),
            )
        )
        print(
            "Wine consumption: {}".format(addThousandSeparator(total_wine_consumption)),
            end="",
        )

        print("\nChoose an option:")
        print("(1) View details of a specific city")
        print("(2) View building summary for all cities")
        print("(3) View resources summary for all cities")
        option = read(min=1, max=3, digit=True)

        if option == 1:
            print("\nOf which city do you want to see the state?")
            city = chooseCity(session)
            banner()

            (wood, good, typeGood) = getProductionPerSecond(session, city["id"])
            print(
                "\033[1m{}{}{}".format(
                    color_arr[int(typeGood)], city["cityName"], color_arr[0]
                )
            )

            resources = city["availableResources"]
            storageCapacity = city["storageCapacity"]
            color_resources = []
            for i in range(len(materials_names)):
                if resources[i] == storageCapacity:
                    color_resources.append(bcolors.RED)
                else:
                    color_resources.append(bcolors.ENDC)
            print("Population:")
            print(
                "{}: {} {}: {}".format(
                    "Housing space",
                    addThousandSeparator(housing_space),
                    "Citizens",
                    addThousandSeparator(citizens),
                )
            )
            print("Storage: {}".format(addThousandSeparator(storageCapacity)))
            print("Resources:")
            for i in range(len(materials_names)):
                print(
                    "{} {}{}{} ".format(
                        materials_names[i],
                        color_resources[i],
                        addThousandSeparator(resources[i]),
                        bcolors.ENDC,
                    ),
                    end="",
                )
            print("")

            print("Production:")
            print(
                "{}: {} {}: {}".format(
                    materials_names[0],
                    addThousandSeparator(wood * 3600),
                    materials_names[typeGood],
                    addThousandSeparator(good * 3600),
                )
            )

            hasTavern = "tavern" in [building["building"] for building in city.get("position", [])]
            if hasTavern:
                consumption_per_hour = city["wineConsumptionPerHour"]
                if consumption_per_hour == 0:
                    print(
                        "{}{}Does not consume wine!{}".format(
                            bcolors.RED, bcolors.BOLD, bcolors.ENDC
                        )
                    )
                else:
                    if typeGood == 1 and (good * 3600) > consumption_per_hour:
                        elapsed_time_run_out = "∞"
                    else:
                        consumption_per_second = Decimal(consumption_per_hour) / Decimal(
                            3600
                        )
                        remaining_resources_to_consume = Decimal(resources[1]) / Decimal(
                            consumption_per_second
                        )
                        elapsed_time_run_out = daysHoursMinutes(
                            remaining_resources_to_consume
                        )
                    print("There is wine for: {}".format(elapsed_time_run_out))

            for building in [
                building for building in city.get("position", []) if building["name"] != "empty"
            ]:
                if building["isMaxLevel"] is True:
                    color = bcolors.BLACK
                elif building["canUpgrade"] is True:
                    color = bcolors.GREEN
                else:
                    color = bcolors.RED

                level = building["level"]
                if level < 10:
                    level = " " + str(level)
                else:
                    level = str(level)
                if building["isBusy"] is True:
                    level = level + "+"

                print(
                    "lv:{}\t{}{}{}".format(level, color, building["name"], bcolors.ENDC)
                )

            enter()
            print("")
            event.set()

        elif option == 2:
            banner()
            print("\nBuilding summary for all cities:\n")

            # Obter os dados de todas as cidades
            cities = getAllCitiesInfo(session)

            # Criar lista de todos os edifícios existentes
            building_names = set()
            for city_data in cities.values():
                if "position" in city_data:
                    for building in city_data["position"]:
                        if building["name"] != "empty":  # Ignorar espaços vazios
                            building_names.add(building["name"])

            # Verificar se há edifícios para exibir
            if not building_names:
                print("No buildings found in any city.")
                enter()
                event.set()
                return

            # Ordenar os edifícios alfabeticamente
            building_names = sorted(building_names)

            # Criar cabeçalho da tabela
            print("{:<20}".format("City"), end="|")
            for building in building_names:
                print("{:>10}".format(building), end="|")
            print()

            # Estrutura de dados para o JSON
            empire_data = {}

            # Preencher os dados de cada cidade
            for city_data in cities.values():
                city_name = city_data.get("name", "Unknown")
                print("{:<20}".format(city_name), end="|")
                
                # Dicionário para armazenar os níveis dos edifícios da cidade
                city_buildings = {}

                for building in building_names:
                    level = ""  # Caso o edifício não esteja presente
                    if "position" in city_data:
                        for b in city_data["position"]:
                            if b["name"] == building:
                                level = str(b.get("level", ""))
                                if b.get("isBusy"):  # Se estiver em construção, adicionar "+"
                                    level += "+"
                                break
                    print("{:>10}".format(level), end="|")
                    city_buildings[building] = level
                print()

                # Adicionar os dados da cidade ao império
                empire_data[city_name] = city_buildings

            # Gravar os dados no ficheiro JSON
            logs_dir = "/tmp/ikalogs/"
       

            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            empire_json_path = os.path.join(logs_dir, "empire.json")
            with open(empire_json_path, "w") as json_file:
                json.dump(empire_data, json_file, indent=4)

            print(f"\nData saved to {empire_json_path}")

            enter()
            print("")
            event.set()

        elif option == 3:
            banner()
            print("\nResources summary for all cities:\n")

            # Obter os dados de todas as cidades
            cities = getAllCitiesInfo(session)

            # Criar lista de todos os recursos
            resource_names = materials_names_english

            # Verificar se há cidades para exibir
            if not cities:
                print("No cities found.")
                enter()
                event.set()
                return

            # Criar cabeçalho da tabela
            print("{:<20}".format("City"), end="|")
            for resource in resource_names:
                print("{:>10}".format(resource), end="|")
            print()

            # Estrutura de dados para o JSON
            resources_data = {}

            # Preencher os dados de cada cidade
            for city_data in cities.values():
                city_name = city_data.get("name", "Unknown")
                print("{:<20}".format(city_name), end="|")

                # Dicionário para armazenar os recursos da cidade
                city_resources = {}

                for i, resource in enumerate(resource_names):
                    resource_value = city_data["availableResources"][i]
                    print("{:>10}".format(addThousandSeparator(resource_value)), end="|")
                    city_resources[resource] = resource_value
                print()

                # Adicionar os dados da cidade ao dicionário de recursos
                resources_data[city_name] = city_resources

            # Gravar os dados no ficheiro JSON
            logs_dir = "/tmp/ikalogs/"
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            resources_json_path = os.path.join(logs_dir, "resources.json")
            with open(resources_json_path, "w") as json_file:
                json.dump(resources_data, json_file, indent=4)

            print(f"\nData saved to {resources_json_path}")

            enter()
            print("")
            event.set()

    except KeyboardInterrupt:
        event.set()
        return