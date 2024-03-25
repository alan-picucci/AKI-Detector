FROM ubuntu:jammy
ARG local="datab"
ARG dir="datac"
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -yq install python3-pip \
    && apt-get clean
COPY requirements.txt /
RUN pip3 install -r /requirements.txt
COPY inference/inference.py /inference/
COPY README.md /
COPY model/model.pkl /model/
COPY model/model_noagesex.pkl /model/
COPY inference/communication.py /inference/
COPY inference/database.py /inference
COPY tests/mock_history.csv /tests/
COPY tests/test_history.csv /tests/
COPY inference/communication_test.py /inference/
COPY inference/inference_tests.py /inference/
COPY inference/database_test.py /inference/
COPY test.sh /
COPY data/history.csv /${local}/
COPY data/aki.csv /${local}/
RUN mkdir /${dir}/
ENV MLLP_ADDRESS="host.docker.internal:8440"
ENV PAGER_ADDRESS="host.docker.internal:8441"
RUN chmod +x test.sh
RUN chmod +x /inference/communication.py
RUN sh test.sh
CMD ["python3","-u","./inference/communication.py"]
