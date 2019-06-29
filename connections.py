import click
from pprint import PrettyPrinter
from requests_html import HTMLSession


@click.command()
@click.option('--source', help='Source destination i.e. Praha')
@click.option('--destination', help='Target destination i.e. Brno')
@click.option('--departure_date', help='Date when you want to leave i.e. 2019-06-30')
def find_connections(source, destination, departure_date):
    try:
        j = Journeys(Destinations("cs"))
        journeys = j.get_journeys(departure_date, from_name=source, to_name=destination)
        pp = PrettyPrinter()
        pp.pprint(journeys)
    except DestinationException as not_found_exception:
        print(not_found_exception)
        exit(1)


class DestinationException(Exception):
    pass


class Destinations:
    def __init__(self, lang):
        self.lang = lang
        ds_json = self.get_destinations_json()
        self.destinations_by_name = self.prepare_destinations_by_name(ds_json)
        self.destinations_by_id = self.prepare_destinations_by_id(ds_json)

    def get_destinations_json(self):
        destinations_url = f"https://www.studentagency.cz/shared/wc/ybus-form/destinations-{self.lang}.json"
        return HTMLSession().get(destinations_url).json()

    @staticmethod
    def prepare_destinations_by_name(destinations_json):
        destinations = {}
        for country in destinations_json["destinations"]:
            for city in country["cities"]:
                destinations[city["name"]] = city["id"]
        return destinations

    @staticmethod
    def prepare_destinations_by_id(destinations_json):
        destinations = {}
        for country in destinations_json["destinations"]:
            for city in country["cities"]:
                destinations[city["id"]] = city["name"]
        return destinations

    def get_destination_id(self, name):
        if not name in self.destinations_by_name:
            raise DestinationException(f"Destination {name} not found")
        return self.destinations_by_name[name]

    def get_destination_name(self, destination_id):
        if not destination_id in self.destinations_by_id:
            raise DestinationException(f"Destination {destination_id} not found")
        return self.destinations_by_id[destination_id]


class Journeys:
    def __init__(self, destinations):
        self.destinations = destinations

    def get_journeys_json(self, departure_date, from_location_id, to_location_id):
        journeys_url = f"https://brn-ybus-pubapi.sa.cz/restapi/routes/search/simple?locale=cz&departureDate={departure_date}&fromLocationId={from_location_id}&toLocationId={to_location_id}&fromLocationType=CITY&toLocationType=CITY&tariffs=REGULAR"
        return HTMLSession().get(journeys_url).json()

    def get_journeys(self, departure_date, from_name, to_name):
        from_location_id = self.destinations.get_destination_id(from_name)
        to_location_id = self.destinations.get_destination_id(to_name)
        js_json = self.get_journeys_json(departure_date, from_location_id, to_location_id)
        journeys = []
        for route in js_json["routes"]:
            if route["freeSeatsCount"] <= 0:
                continue

            journeys.append({
                "departure_datetime": route["departureTime"],
                "arrival_datetime": route["arrivalTime"],
                "source": to_name,
                "destination": from_name,
                "price": route["priceFrom"],  # in EUR - you can use https://api.skypicker.com/rates
                "type": route["vehicleTypes"][0].lower(),  # optional (bus/train)
                "source_id": from_location_id,  # optional (carrier’s id)
                "destination_id": to_location_id,  # optional (carrier’s id)
                "free_seats": route["freeSeatsCount"],  # optional
                "carrier": "Regiojet",  # optional
            })
        return journeys


if __name__ == '__main__':
    find_connections()
