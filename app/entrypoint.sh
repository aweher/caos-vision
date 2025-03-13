#!/bin/bash
if [ "$1" = "--production" ]; then
    exec socketio.run(app, host='0.0.0.0', debug=False, allow_unsafe_werkzeug=True)
else
    exec socketio.run(app, host='0.0.0.0', debug=True)
fi