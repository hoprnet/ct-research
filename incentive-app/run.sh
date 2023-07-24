echobold(){
    GREEN='\e[1;42m'
    NC='\033[0m'
    printf "\e[1;42m${1}\033[0m\n"
}

die() {
    printf '%s\n' "$1" >&2
    exit 1
}

module=
port=
host=
route=
key=
aggpost=
rcphendpoint=
subgraphurl=
scaddress=
db=
dbhost=
dbuser=
dbpass=
dbport=

while :; do
    case $1 in
        --module)
            if [ "$2" ]; then
                module=$2
                shift
            else
                die 'ERROR: "--module" requires a non-empty option argument.'
            fi
            ;;
        --port)
            if [ "$2" ]; then
                port=$2
                shift
            else
                die 'ERROR: "--port" requires a non-empty option argument.'
            fi
            ;;
        --host)
            if [ "$2" ]; then
                host=$2
                shift
            else
                die 'ERROR: "--host" requires a non-empty option argument.'
            fi
            ;;
        --route)
            if [ "$2" ]; then
                route=$2
                shift
            else
                die 'ERROR: "--route" requires a non-empty option argument.'
            fi
            ;;
        --key)
            if [ "$2" ]; then
                key=$2
                shift
            else
                die 'ERROR: "--key" requires a non-empty option argument.'
            fi
            ;;
        --aggpost)
            if [ "$2" ]; then
                aggpost=$2
                shift
            else
                die 'ERROR: "--aggpost" requires a non-empty option argument.'
            fi
            ;;
        --rcphendpoint)
            if [ "$2" ]; then
                rcphendpoint=$2
                shift
            else
                die 'ERROR: "--rcphendpoint" requires a non-empty option argument.'
            fi
            ;;
        --subgraphurl)
            if [ "$2" ]; then
                subgraphurl=$2
                shift
            else
                die 'ERROR: "--subgraphurl" requires a non-empty option argument.'
            fi
            ;;
        --scaddress)
            if [ "$2" ]; then
                scaddress=$2
                shift
            else
                die 'ERROR: "--scaddress" requires a non-empty option argument.'
            fi
            ;;
        --db)
            if [ "$2" ]; then
                db=$2
                shift
            else
                die 'ERROR: "--db" requires a non-empty option argument.'
            fi
            ;;
        --dbhost)
            if [ "$2" ]; then
                dbhost=$2
                shift
            else
                die 'ERROR: "--dbhost" requires a non-empty option argument.'
            fi
            ;;
        --dbuser)
            if [ "$2" ]; then
                dbuser=$2
                shift
            else
                die 'ERROR: "--dbuser" requires a non-empty option argument.'
            fi
            ;;
        --dbpass)
            if [ "$2" ]; then
                dbpass=$2
                shift
            else
                die 'ERROR: "--dbpass" requires a non-empty option argument.'
            fi
            ;;
        --dbport)
            if [ "$2" ]; then
                dbport=$2
                shift
            else
                die 'ERROR: "--dbport" requires a non-empty option argument.'
            fi
            ;;
        --)              # End of all options.
            shift
            break
            ;;
        -?*)
            printf 'WARN: Unknown option (ignored): %s\n' "$1" >&2
            ;;
        *)               # Default case: No more options, so break out of the loop.
            break
    esac

    shift
done

if [ "$module" = "netwatcher" ]; then
    if [ -z "$port" ]; then
        echo "Error: --port parameter is required"
        exit 1
    fi
    if [ -z "$host" ]; then
        echo "Error: --host parameter is required"
        exit 1
    fi
    if [ -z "$key" ]; then
        echo "Error: --key parameter is required"
        exit 1
    fi
    if [ -z "$aggpost" ]; then
        echo "Error: --aggpost parameter is required"
        exit 1
    fi

    clear
    echobold "Running Netwatcher"
    python -m netwatcher --port $port --apihost $host --apikey $key --aggpost $aggpost

elif [ "$module" = "aggregrator" ]; then
    if [ -z "$host" ]; then
        echo "Error: --host parameter is required"
        exit 1
    fi
    if [ -z "$port" ]; then
        echo "Error: --port parameter is required"
        exit 1
    fi
    if [ -z "$db" ]; then
        echo "Error: --db parameter is required"
        exit 1
    fi
    if [ -z "$dbhost" ]; then
        echo "Error: --dbhost parameter is required"
        exit 1
    fi
    if [ -z "$dbuser" ]; then
        echo "Error: --dbuser parameter is required"
        exit 1
    fi
    if [ -z "$dbpass" ]; then
        echo "Error: --dbpass parameter is required"
        exit 1
    fi
    if [ -z "$dbport" ]; then
        echo "Error: --dbport parameter is required"
        exit 1
    fi

    clear
    echobold "Running Aggregator"
    python -m aggregator --host $host --port $port --db $db --dbhost $dbhost --dbuser $dbuser --dbpass $dbpass --dbport $dbport

elif [ "$module" = "aggtrigger" ]; then
    if [ -z "$host" ]; then
        echo "Error: --host parameter is required"
        exit 1
    fi
    if [ -z "$port" ]; then
        echo "Error: --port parameter is required"
        exit 1
    fi
    if [ -z "$route" ]; then
        echo "Error: --route parameter is required"
        exit 1
    fi
    clear
    echobold "Running Trigger"
    python -m aggregator_trigger --host $host --port $port --route $route

elif [ "$module" = "economic_handler" ]; then
    if [ -z "$port" ]; then
        echo "Error: --port parameter is required"
        exit 1
    fi
    if [ -z "$host" ]; then
        echo "Error: --host parameter is required"
        exit 1
    fi
    if [ -z "$key" ]; then
        echo "Error: --key parameter is required"
        exit 1
    fi
    if [ -z "$rcphendpoint" ]; then
        echo "Error: --rcphendpoint parameter is required"
        exit 1
    fi
    if [ -z "$subgraphurl" ]; then
        echo "Error: --subgraphurl parameter is required"
        exit 1
    fi
    if [ -z "$scaddress" ]; then
        echo "Error: --scaddress parameter is required"
        exit 1
    fi

    clear
    echobold "Running Economic Handler"
    python -m economic_handler  --port $port --apihost $host --apikey $key --rcphnodes $rcphendpoint --subgraphurl $subgraphurl --scaddress $scaddress

else
    echobold "Tried to run unknown module: '$module'"

fi


# netwatcher: ./run.sh -m nw -p 13301 -h localhost -k "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%" -a "http://localhost:8080/aggregator/list"
# trigger: ./run.sh -m trigger -h localhost -p 8080 -r /aggregator/to_db
# aggregator: ./run.sh -m agg -h localhost -p 8080
# economic_handler: ./run.sh --module  economic_handler --port 13301 --host "127.0.0.1" --key "%th1s-IS-a-S3CR3T-ap1-PUSHING-b1ts-TO-you%" --rcphendpoint "some_api_endpoint_test"

