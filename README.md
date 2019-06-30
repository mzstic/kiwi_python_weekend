# kiwi_python_weekend

You should be able to build and run it in docker container like this:
```docker build . -t py_weekend
docker run -p 5000:5000 -e PORT=5000 py_weekend
```

Maybe redis / SQL won't exist anymore, change it to something else :)

On http://localhsot:5000/search you should see form which communicates via ajax with backends and automatically renders response into table below.
