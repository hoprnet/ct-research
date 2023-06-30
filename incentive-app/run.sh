echobold(){
    GREEN='\e[1;42m'
    NC='\033[0m'
    printf "\e[1;42m${1}\033[0m\n"
}


while getopts :m:p:u:h:r:k:a:e: flag
do
    case "${flag}" in
        m) module=${OPTARG};;
        p) port=${OPTARG};;
        h) host=${OPTARG};;
        r) route=${OPTARG};;
        k) key=${OPTARG};;
        a) aggpost=${OPTARG};;
        e) rcphendpoint=${OPTARG};;

    esac
done


if [ "$module" = "nw" ]; then
    if [ -z "$port" ]; then
        echo "Error: -p parameter is required"
        exit 1
    fi
    if [ -z "$host" ]; then
        echo "Error: -h parameter is required"
        exit 1
    fi
    if [ -z "$key" ]; then
        echo "Error: -k parameter is required"
        exit 1
    fi
    if [ -z "$aggpost" ]; then
        echo "Error: -a parameter is required"
        exit 1
    fi

    clear
    echobold "Running Netwatcher"
    python -m netwatcher --port $port --apihost $host --apikey $key --aggpost $aggpost
    
elif [ "$module" = "agg" ]; then
    if [ -z "$host" ]; then
        echo "Error: -h parameter is required"
        exit 1
    fi
    if [ -z "$port" ]; then
        echo "Error: -p parameter is required"
        exit 1
    fi
    clear
    echobold "Running Aggregator"
    python -m aggregator --host $host --port $port 
elif [ "$module" = "trigger" ]; then
    if [ -z "$host" ]; then
        echo "Error: -h parameter is required"
        exit 1
    fi
    if [ -z "$port" ]; then
        echo "Error: -p parameter is required"
        exit 1
    fi
    if [ -z "$route" ]; then
        echo "Error: -r parameter is required"
        exit 1
    fi
    clear
    echobold "Running Trigger"
    python -m aggregator_trigger --host $host --port $port --route $route



elif [ "$module" = "economic" ]; then
    if [ -z "$port" ]; then
        echo "Error: -p parameter is required"
        exit 1
    fi
    if [ -z "$host" ]; then
        echo "Error: -h parameter is required"
        exit 1
    fi
    if [ -z "$key" ]; then
        echo "Error: -k parameter is required"
        exit 1
    fi
    if [ -z "$rcphendpoint" ]; then
        echo "Error: -e parameter is required"
        exit 1
    fi

    clear
    echobold "Running Economic Handler"
    python -m economic_handler  --port $port --apihost $host --apikey $key --rcphnodes $rcphendpoint
else
    echobold "Tried to run unknown module: '$module'"
fi


# netwatcher: ./run.sh -m nw -p 13301 -h localhost -k "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%" -a "http://localhost:8080/aggregator/list"
#    trigger: ./run.sh -m trigger -h localhost -p 8080 -r /aggregator/to_db
# aggregator: ./run.sh -m agg -h localhost -p 8080
#   economic: ./run.sh -m economic -p 13301 -h localhost -k "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%" -e 'some_api_endpoint_test'

