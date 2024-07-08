export $(grep -v '^#' .env | xargs)

env=${1:staging}
count=${2:1}

healthyz() { echo $(curl -s -o /dev/null -w "%{http_code}" "${env}/healthyz"); }

check_deployment() {
    if [ $(healthyz $(printf $env "blue" "1" $count)) -eq 200 ]; then
        echo "blue"
        exit 1
    elif [ $(healthyz $(printf $env "green" "1" $count)) -eq 200 ]; then
        echo "green"
        exit 1
    fi
}

deployment=$(check_deployment $HOST_FORMAT $env)


# Node parameters
for i in $(seq 1 $count); do
    export NODE_ADDRESS_${i}=$(printf $HOST_FORMAT $deployment $i $env)
    export NODE_KEY_${i}=$TOKEN
done

python -m core --configfile ./.configs/core_${env}_config.yaml