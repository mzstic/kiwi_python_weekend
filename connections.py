import click
from pprint import PrettyPrinter
from requests_html import HTMLSession
from dateutil.parser import parse
from slugify import slugify
from redis import StrictRedis
import json
import psycopg2
from psycopg2.extras import RealDictCursor


@click.command()
@click.option("--source", help="Source destination i.e. Praha")
@click.option("--destination", help="Target destination i.e. Brno")
@click.option("--departure_date", help="Date when you want to leave i.e. 2019-06-30")
def run(source, destination, departure_date):
    conns = find_connections(source, destination, departure_date)
    pp = PrettyPrinter()
    pp.pprint(conns)


def find_connections(source, destination, departure_date):
    redis_config = {
        "host": "157.230.124.217",
        "password": "akd89DSk23Kldl0ram",
        "port": 6379,
    }
    redis = StrictRedis(socket_connect_timeout=3, **redis_config)

    pg_config = {
        "host": "pythonweekend.cikhbyfn2gm8.eu-west-1.rds.amazonaws.com",
        "database": "pythonweekend",
        "user": "shareduser",
        "password": "NeverEverSharePasswordsInProductionEnvironement",
    }

    db_connection = psycopg2.connect(**pg_config)

    # euro = EurolinesJourneys(EurolinesDestinations())
    # euroJourneys = euro.get_journeys(departure_date, from_name=source, to_name=destination)

    regio = RegiojetJourneys(redis, RegiojetDestinations(redis))
    regiojet_journeys = regio.get_journeys(
        departure_date, from_name=source, to_name=destination
    )

    for j in regiojet_journeys:
        save_journey_to_db(db_connection, j)

    return regiojet_journeys


def save_journey_to_db(conn, journey):
    sql_insert = """
        INSERT INTO journeys_mp (
            source, 
            destination, 
            departure_datetime, 
            arrival_datetime, 
            carrier,
            vehicle_type,
            price, 
            currency
        )
        VALUES (
            %(source)s,
            %(destination)s,
            %(departure_datetime)s,
            %(arrival_datetime)s,
            %(carrier)s,
            %(vehicle_type)s,
            %(price)s,
            %(currency)s
        )
        ;
    """
    values = {
        "source": journey["source"],
        "destination": journey["destination"],
        "departure_datetime": journey["departure_datetime"],
        "arrival_datetime": journey["arrival_datetime"],
        "carrier": journey["carrier"],
        "vehicle_type": journey["type"],
        "price": journey["price"],
        "currency": "EUR",
    }
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        try:
            cursor.execute(sql_insert, values)  # psycopg2 statement execution syntax
            conn.commit()  # important, otherwise your data won't be inserted!
        except:
            pass

    # departure_time & arrival_time should be datetime object, psycopg2 will format them for you


def get_all_destinations():
    redis_config = {
        "host": "157.230.124.217",
        "password": "akd89DSk23Kldl0ram",
        "port": 6379,
    }
    redis = StrictRedis(socket_connect_timeout=3, **redis_config)
    regio_dests = RegiojetDestinations(redis)
    return regio_dests.get_all_destinations()


class DestinationException(Exception):
    pass


class EurolinesJourneys:
    def __init__(self, destinations):
        self.destinations = destinations

    def get_journeys_json(self, departure_date, from_location_id, to_location_id):
        journeys_url = f"https://back.eurolines.eu/euroline_api/journeys?date={departure_date}&originCity={from_location_id}&destinationCity={to_location_id}"
        return HTMLSession().get(journeys_url).json()

    def get_journeys(self, departure_date, from_name, to_name):
        try:
            from_location_id = self.destinations.get_destination_id(from_name)
            to_location_id = self.destinations.get_destination_id(to_name)
        except DestinationException as e:
            return []

        js_json = self.get_journeys_json(
            departure_date, from_location_id, to_location_id
        )
        journeys = []
        for route in js_json:
            dd = parse(route["departure"])
            ad = parse(route["arrival"])
            journeys.append(
                {
                    "departure_datetime": dd.strftime("%Y-%m-%d %H:%M:%S"),
                    "arrival_datetime": ad.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": from_name,
                    "destination": to_name,
                    "price": route[
                        "price"
                    ],  # in EUR - you can use https://api.skypicker.com/rates
                    "type": "bus",  # optional (bus/train)
                    "source_id": from_location_id,  # optional (carrier's id)
                    "destination_id": to_location_id,  # optional (carrier's id)
                    "free_seats": route["remaining"],  # optional
                    "carrier": "Eurolines",  # optional
                }
            )
        return journeys


class EurolinesDestinations:
    def __init__(self):
        self.destinations_by_name = {}
        self.destinations_by_id = {}

    def get_destination_id(self, name):
        destinations_url = f"https://back.eurolines.eu/euroline_api/origins?q={name}"
        r = HTMLSession().get(destinations_url)
        json = r.json()
        if len(json) == 0:
            raise DestinationException(
                f"Destination {name} not found in Eurolines module"
            )
        d = json[0]
        self.destinations_by_name[d["name"]] = d["id"]
        self.destinations_by_name[d["id"]] = d["name"]
        return d["id"]

    def get_destination_name(self, destination_id):
        return self.destinations_by_id[destination_id]


class RegiojetDestinations:
    def __init__(self, redis, lang="cs"):
        self.lang = lang
        self.redis = redis
        self.carrier_name = "regiojet"

    def get_destinations_json(self):
        destinations_url = f"https://www.studentagency.cz/shared/wc/ybus-form/destinations-{self.lang}.json"
        return HTMLSession().get(destinations_url).json()

    def get_all_destinations(self):
        all_dests = self.redis.get(get_all_destinations_cache_key(self.carrier_name))
        if all_dests is not None:
            return json.loads(all_dests.decode())
        self.fill_destinations_cache(self.get_destinations_json())
        return json.loads(
            self.redis.get(get_all_destinations_cache_key(self.carrier_name)).decode()
        )

    def fill_destinations_cache(self, destinations_json):
        all_destinations = []
        for country in destinations_json["destinations"]:
            for city in country["cities"]:
                self.redis.setex(
                    get_destination_cache_key(city["name"], self.carrier_name),
                    60 * 60,
                    city["id"],
                )
                all_destinations.append(city["name"])
        self.redis.setex(
            get_all_destinations_cache_key(self.carrier_name),
            60 * 60,
            json.dumps(all_destinations),
        )

    def get_destination_id(self, name):
        data_from_redis = self.redis.get(
            get_destination_cache_key(name, self.carrier_name)
        )
        if data_from_redis is not None:
            return data_from_redis.decode()
        self.fill_destinations_cache(self.get_destinations_json())
        data_from_redis = self.redis.get(
            get_destination_cache_key(name, self.carrier_name)
        )
        if data_from_redis is None:
            raise DestinationException(
                f"Destination {name} not found for carrier {self.carrier_name}"
            )
        return data_from_redis.decode()


class RegiojetJourneys:
    def __init__(self, redis, destinations):
        self.destinations = destinations
        self.redis = redis
        self.cache_ttl = 60 * 60
        self.carrier_name = "regiojet"

    def get_journeys_json(self, departure_date, from_location_id, to_location_id):
        journeys_url = f"https://brn-ybus-pubapi.sa.cz/restapi/routes/search/simple?locale=cz&departureDate={departure_date}&fromLocationId={from_location_id}&toLocationId={to_location_id}&fromLocationType=CITY&toLocationType=CITY&tariffs=REGULAR"
        return HTMLSession().get(journeys_url).json()

    def get_journeys(self, departure_date, from_name, to_name):
        try:
            from_location_id = self.destinations.get_destination_id(from_name)
            to_location_id = self.destinations.get_destination_id(to_name)
        except DestinationException as e:
            return []

        cache_key = get_journey_cache_key(
            departure_date, from_name, to_name, self.carrier_name
        )
        cached_journeys = self.redis.get(cache_key)
        if cached_journeys is not None:
            return json.loads(cached_journeys.decode())

        js_json = self.get_journeys_json(
            departure_date, from_location_id, to_location_id
        )
        journeys = []
        for route in js_json["routes"]:
            # if route["freeSeatsCount"] <= 0:
            #     continue

            dd = parse(route["departureTime"])
            ad = parse(route["arrivalTime"])

            if dd.strftime("%Y-%m-%d") != departure_date:
                continue

            journeys.append(
                {
                    "departure_datetime": dd.strftime("%Y-%m-%d %H:%M:%S"),
                    "arrival_datetime": ad.strftime("%Y-%m-%d %H:%M:%S"),
                    "source": from_name,
                    "destination": to_name,
                    "price": route[
                        "priceFrom"
                    ],  # in EUR - you can use https://api.skypicker.com/rates
                    "type": route["vehicleTypes"][0].lower(),  # optional (bus/train)
                    "source_id": from_location_id,  # optional (carrier's id)
                    "destination_id": to_location_id,  # optional (carrier's id)
                    "free_seats": route["freeSeatsCount"],  # optional
                    "carrier": "Regiojet",  # optional
                }
            )
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(journeys))
        return journeys


def get_journey_cache_key(departure_date, from_name, to_name, carrier):
    return f"prg_pw2:journey:{slugify(from_name)}_{slugify(to_name)}_{departure_date}_{carrier}"


def get_all_destinations_cache_key(carrier):
    return f"prg_pw2:location:all_{carrier}"


def get_destination_cache_key(location_name, carrier):
    return f"prg_pw2:location:{slugify(location_name)}_{carrier}"


if __name__ == "__main__":
    conns = run()
