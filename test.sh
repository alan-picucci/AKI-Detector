#!/bin/bash
cd inference
python3 -m communication_test -v
python3 -m inference_tests -v
python3 -m database_test -v
ret=$?
if [ $ret -ne 0 ]; then
        echo "At least one test failed"
else
        echo "All tests ran succesfully"
fi