from flask import request, jsonify, Flask, render_template
import connections
from forms import SearchForm
from dateutil.parser import parse
from datetime import timedelta

app = Flask(__name__)
app.config["PROPAGATE_EXCEPTIONS"] = True


@app.route("/search", methods=["GET", "POST"])
def search():
    form = SearchForm(csrf_enabled=False)
    if form.validate_on_submit():
        date_from = request.form.get("date_from")
        date_to = request.form.get("date_to")
        source = request.form.get("source")
        destination = request.form.get("destination")
        count = int(request.form.get("count"))

        conns = []
        d_from = parse(date_from)
        d_to = parse(date_to)
        delta = d_to - d_from
        for i in range(delta.days + 1):
            new_conns = connections.find_connections(
                source,
                destination,
                departure_date=(d_from + timedelta(days=i)).strftime("%Y-%m-%d"),
            )
            conns += new_conns

        return render_template(
            "search_results.html",
            journeys=conns,
            form=form,
            source=source,
            destination=destination,
            count=count,
            date_from=date_from,
            date_to=date_to,
        )

    return render_template("search_vue.html", form=form)


@app.route("/whisperer", methods=["GET"])
def whisper():
    term = request.args.get("term", "").lower()
    destinations = connections.get_all_destinations()
    return jsonify([x for x in destinations if term in x.lower()])


if __name__ == "__main__":
    app.run(debug=True)
