#! /bin/bash

set -o pipefail
set -e
SECONDS=0
if [ -z "${LAB_NAME}" ]; then
  read -rp "Enter the name of your lab, press enter to skip: " LAB_NAME
  export LAB_NAME="${LAB_NAME:-RegionOne}"
fi

if [ -z "${ACME_EMAIL}" ]; then
  read -rp "Enter a valid email address for use with ACME, press enter to skip: " ACME_EMAIL
  export ACME_EMAIL="${ACME_EMAIL:-}"
fi

if [ -z "${GATEWAY_DOMAIN}" ]; then
  echo "The domain name for the gateway is required, if you do not have a domain name press enter to use the default"
  read -rp "Enter the domain name for the gateway [cluster.local]: " GATEWAY_DOMAIN
  export GATEWAY_DOMAIN="${GATEWAY_DOMAIN:-cluster.local}"
fi

kubectl label node $(kubectl get nodes | awk '/controller/ {print $1}') openstack-control-plane=enabled
kubectl label node $(kubectl get nodes | awk '/compute/ {print $1}') openstack-compute-node=enabled
kubectl label node $(kubectl get nodes | awk '/network/ {print $1}') openstack-network-node=enabled
kubectl label node $(kubectl get nodes | awk '/storage/ {print $1}') openstack-storage-node=enabled
kubectl label node $(kubectl get nodes | awk '/ceph/ {print $1}') role=storage-node
kubectl label node $(kubectl get nodes | awk '/compute/ {print $1}') openstack-network-node=enabled
kubectl label node $(kubectl get nodes | awk '/worker/ {print $1}')  node-role.kubernetes.io/worker=worker
kubectl label node -l beta.kubernetes.io/os=linux kubernetes.io/os=linux
kubectl label node -l node-role.kubernetes.io/control-plane kube-ovn/role=master
kubectl label node -l ovn.kubernetes.io/ovs_dp_type!=userspace ovn.kubernetes.io/ovs_dp_type=kernel
kubectl label node -l node-role.kubernetes.io/control-plane longhorn.io/storage-node=enabled
# kubectl label node longhorn0{1..3}.cluster.local longhorn.io/storage-node=enabled
kubectl get nodes -o json | jq '[.items[] | {"NAME": .metadata.name, "LABELS": .metadata.labels}]'
kubectl apply -k /etc/genestack/kustomize/k8s-dashboard
if kubectl taint nodes -l node-role.kubernetes.io/control-plane node-role.kubernetes.io/control-plane:NoSchedule-; then
    echo "Taint removed"
else
    echo "No Taint found"
fi

cat <<'EOF' > /etc/genestack/helm-configs/kube-ovn/kube-ovn-helm-overrides.yaml
networking:
  IFACE: "enp4s0"
  vlan:
    VLAN_INTERFACE_NAME: "enp4s0"
EOF
/opt/genestack/bin/install-kube-ovn.sh
echo "Sleeping for 2 minutes to let OVN deploy"
sleep 120
/opt/genestack/bin/install-prometheus.sh
echo "Sleeping for 2 minutes to let prometheus deploy"
sleep 120
pod_count=$(kubectl -n prometheus get pods -l "release=kube-prometheus-stack" --no-headers | wc -l)

if [[ $pod_count -ge 2 ]]; then
    echo "Prometheus pods are created"
else
    echo "Problem with prometheus pods.  Droping out of script"
    # exit 1
fi

echo "Deploy Ceph(internal)"
echo "Deploying Rook Operator"
kubectl apply -k /etc/genestack/kustomize/rook-operator/base
echo "Sleeping for 30 seconds"
sleep 30
kubectl -n rook-ceph set image deploy/rook-ceph-operator rook-ceph-operator=rook/ceph:v1.16.5
echo "Label Storage nodes"
for node in storage0{1..3}.cluster.local;do kubectl label node $node role=storage-node ;done
echo "Deploy Rook cluster"
kubectl apply -k /etc/genestack/kustomize/rook-cluster/overlay
echo "Sleeping for 3 minutes"
sleep 180
# Validate the cluster is operational
kubectl --namespace rook-ceph get cephclusters.ceph.rook.io
kubectl --namespace rook-ceph get pods 
echo "Create Storage Classes"
kubectl apply -k /etc/genestack/kustomize/rook-defaults
echo "Sleeping for 30 seconds"
sleep 30
cat <<'EOF' > /etc/genestack/helm-configs/longhorn/longhorn.yaml
---
longhornDriver:
  nodeSelector:
    longhorn.io/storage-node: "enabled"
longhornUI:
  nodeSelector:
    longhorn.io/storage-node: "enabled"
longhornConversionWebhook:
  nodeSelector:
    longhorn.io/storage-node: "enabled"
longhornAdmissionWebhook:
  nodeSelector:
    longhorn.io/storage-node: "enabled"
longhornRecoveryBackend:
  nodeSelector:
    longhorn.io/storage-node: "enabled"
EOF
kubectl apply -f /etc/genestack/manifests/longhorn/longhorn-namespace.yaml
/opt/genestack/bin/install-longhorn.sh
echo "Sleeping for 3 minutes to let longhorn deploy"
sleep 180
cat <<'EOF' > /etc/genestack/manifests/longhorn/longhorn-general-multiattach-storageclass.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: general-multi-attach
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: driver.longhorn.io
allowVolumeExpansion: true
reclaimPolicy: Delete
volumeBindingMode: Immediate
parameters:
  numberOfReplicas: "3"
  dataLocality: "best-effort"
  staleReplicaTimeout: "2880"
  fromBackup: ""
  fsType: "ext4"
  accessMode: "rwx"
EOF
kubectl apply -f /etc/genestack/manifests/longhorn/longhorn-general-multiattach-storageclass.yaml
kubectl apply -k /etc/genestack/kustomize/openstack/overlay
/opt/genestack/bin/create-secrets.sh --region ${LAB_NAME}
find /etc/genestack -type f -exec sed -i "s/RegionOne/${LAB_NAME}/g" {} +
find /opt/genestack -type f -exec sed -i "s/RegionOne/${LAB_NAME}/g" {} +
cat <<'EOF' > /etc/genestack/helm-configs/global_overrides/endpoints.yaml
_region: &region RegionOne

pod:
  resources:
    enabled: false

endpoints:
  compute:
    host_fqdn_override:
      public:
        tls: {}
        host: nova.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  compute_metadata:
    host_fqdn_override:
      public:
        tls: {}
        host: metadata.api.glab.tron.rax.io
    port:
      metadata:
        public: 443
    scheme:
      public: https
  compute_novnc_proxy:
    host_fqdn_override:
      public:
        tls: {}
        host: novnc.api.glab.tron.rax.io
    port:
      novnc_proxy:
        public: 443
    scheme:
      public: https
  cloudformation:
    host_fqdn_override:
      public:
        tls: {}
        host: cloudformation.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  cloudwatch:
    host_fqdn_override:
      public:
        tls: {}
        host: cloudwatch.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  container_infra:
    host_fqdn_override:
      public:
        tls: {}
        host: magnum.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  key_manager:
    host_fqdn_override:
      public:
        tls: {}
        host: barbican.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  dashboard:
    host_fqdn_override:
      public:
        tls: {}
        host: horizon.api.glab.tron.rax.io
    port:
      web:
        public: 443
    scheme:
      public: https
  metric:
    host_fqdn_override:
      public:
        tls: {}
        host: gnocchi.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  identity:
    auth:
      admin:
        region_name: *region
      barbican:
        region_name: *region
      cinder:
        region_name: *region
      ceilometer:
        region_name: *region
      glance:
        region_name: *region
      gnocchi:
        region_name: *region
      heat:
        region_name: *region
      heat_trustee:
        region_name: *region
      heat_stack_user:
        region_name: *region
      ironic:
        region_name: *region
      magnum:
        region_name: *region
      neutron:
        region_name: *region
      nova:
        region_name: *region
      placement:
        region_name: *region
      octavia:
        region_name: *region
    host_fqdn_override:
      public:
        tls: {}
        host: keystone.api.glab.tron.rax.io
    port:
      api:
        public: 443
        admin: 80
    scheme:
      public: https
  ingress:
    port:
      ingress:
        public: 443
  image:
    host_fqdn_override:
      public:
        tls: {}
        host: glance.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  load_balancer:
    host_fqdn_override:
      public:
        tls: {}
        host: octavia.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  network:
    host_fqdn_override:
      public:
        tls: {}
        host: neutron.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  orchestration:
    host_fqdn_override:
      public:
        tls: {}
        host: heat.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  placement:
    host_fqdn_override:
      public:
        tls: {}
        host: placement.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  volume:
    host_fqdn_override:
      public:
        tls: {}
        host: cinder.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  volumev2:
    host_fqdn_override:
      public:
        tls: {}
        host: cinder.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
  volumev3:
    host_fqdn_override:
      public:
        tls: {}
        host: cinder.api.glab.tron.rax.io
    port:
      api:
        public: 443
    scheme:
      public: https
EOF
find /etc/genestack/helm-configs/global_overrides -type f -exec sed -i "s/RegionOne/${LAB_NAME}/g" {} +
cat <<'EOF' > /etc/genestack/helm-configs/global_overrides/logger.yaml
conf:
  logging:
    logger_root:
      level: INFO
      handlers: 'stdout'
EOF
cat <<EOF > /etc/genestack/manifests/metallb/metallb-openstack-service-lb.yml
---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: gateway-api-external
  namespace: metallb-system
spec:
  addresses:
    - 172.31.3.1/32  # This is assumed to be a public LB vip address
  autoAssign: false
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: openstack-external-advertisement
  namespace: metallb-system
spec:
  ipAddressPools:
    - gateway-api-external
  nodeSelectors:  # Optional block to limit nodes for a given advertisement
    - matchLabels:
        kubernetes.io/hostname: controller01.cluster.local
    - matchLabels:
        kubernetes.io/hostname: controller02.cluster.local
    - matchLabels:
        kubernetes.io/hostname: controller03.cluster.local
    - matchLabels:
        kubernetes.io/hostname: controller04.cluster.local
    - matchLabels:
        kubernetes.io/hostname: controller05.cluster.local
  interfaces:  # Optional block to limit ifaces used to advertise VIPs
    - enp3s0
EOF
cat <<'EOF' > /etc/genestack/manifests/metallb/primary.yml
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: primary
  namespace: metallb-system
spec:
  ipAddressPools:
  - primary

---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: primary
  namespace: metallb-system
spec:
  addresses:
  - 10.5.0.0/16
  autoAssign: true
  avoidBuggyIPs: false
EOF
kubectl create -f /etc/genestack/kubesecrets.yaml
kubectl apply -f /etc/genestack/manifests/metallb/metallb-namespace.yaml
/opt/genestack/bin/install-metallb.sh
echo "Sleeping for 2 minutes"
sleep 120
kubectl --namespace metallb-system get deployment.apps/metallb-controller
echo "Sleeping for 30 seconds"
sleep 30
kubectl apply -f /etc/genestack/manifests/metallb/metallb-openstack-service-lb.yml
kubectl apply -f /etc/genestack/manifests/metallb/primary.yml
/opt/genestack/bin/install-envoy-gateway.sh
echo "Sleeping for 15 seconds"
sleep 15
ACME_EMAIL="${ACME_EMAIL}" GATEWAY_DOMAIN="${GATEWAY_DOMAIN}" /opt/genestack/bin/setup-envoy-gateway.sh
echo "Sleeping for 30 seconds"
# Validate
# kubectl -n openstack get httproute
# kubectl -n envoy-gateway get gateways.gateway.networking.k8s.io flex-gateway
sleep 30
/opt/genestack/bin/install-mariadb-operator.sh
echo -e "The operator may take a minute to get ready, before deploying the Galera cluster, wait until the webhook is online."
echo -e "Validate the webhook with kubectl --namespace mariadb-system get pods -w"
read -rp "Press enter to continue when done. "
kubectl --namespace openstack apply -k /etc/genestack/kustomize/mariadb-cluster/overlay
echo "Sleeping for 2 minutes"
sleep 120
kubectl apply -k /etc/genestack/kustomize/rabbitmq-operator
sleep 10
kubectl apply -k /etc/genestack/kustomize/rabbitmq-topology-operator
sleep 10

kubectl apply -k /etc/genestack/kustomize/rabbitmq-cluster/overlay
echo "Sleeping for 2 minutes"
sleep 120
if kubectl --namespace openstack get rabbitmqclusters.rabbitmq.com | grep True; then
    echo "Rabbitmq deployed"
else
    echo "Problem deploying rabbitmq.  Dropping out of script."
    # exit 1
fi
kubectl apply --filename https://raw.githubusercontent.com/rabbitmq/cluster-operator/main/observability/prometheus/monitors/rabbitmq-servicemonitor.yml
kubectl apply --filename https://raw.githubusercontent.com/rabbitmq/cluster-operator/main/observability/prometheus/monitors/rabbitmq-cluster-operator-podmonitor.yml
for file in $(curl -s https://api.github.com/repos/rabbitmq/cluster-operator/contents/observability/prometheus/rules/rabbitmq | jq -r '.[].download_url'); do   kubectl apply -n prometheus -f $file; done
for file in $(curl -s https://api.github.com/repos/rabbitmq/cluster-operator/contents/observability/prometheus/rules/rabbitmq-per-object | jq -r '.[].download_url'); do   kubectl apply -n prometheus -f $file; done
kubectl get prometheusrule -n prometheus -o name | xargs -I {} kubectl label -n prometheus {} release=kube-prometheus-stack --overwrite
/opt/genestack/bin/install-memcached.sh
echo "Sleeping for 2 minutes"
sleep 120
/opt/genestack/bin/install-libvirt.sh
echo "Sleeping for 2 minutes"
sleep 120
kubectl exec -it $(kubectl get pods -l application=libvirt -o=jsonpath='{.items[0].metadata.name}' -n openstack) -n openstack -- virsh list

kubectl annotate nodes -l openstack-compute-node=enabled -l openstack-network-node=enabled ovn.openstack.org/int_bridge='br-int'
kubectl annotate nodes -l openstack-compute-node=enabled -l openstack-network-node=enabled ovn.openstack.org/bridges='br-ex'
kubectl annotate nodes -l openstack-compute-node=enabled -l openstack-network-node=enabled ovn.openstack.org/ports='br-ex:enp5s0'
kubectl annotate nodes -l openstack-compute-node=enabled -l openstack-network-node=enabled ovn.openstack.org/mappings='physnet1:br-ex'
kubectl annotate nodes -l openstack-compute-node=enabled -l openstack-network-node=enabled ovn.openstack.org/availability_zones='az1'
kubectl annotate nodes -l openstack-network-node=enabled ovn.openstack.org/gateway='enabled'
kubectl apply -k /etc/genestack/kustomize/ovn
echo "Sleeping for 60 seconds"
sleep 60
kubectl -n kube-system patch deployment kube-ovn-controller -p '{"spec":{"template":{"spec":{"nodeSelector":{"kube-ovn/role":"master","kubernetes.io/os":"linux"}}}}}'
/opt/genestack/bin/install-fluentbit.sh
echo "Sleeping for 5 seconds"
sleep 5
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
cp /opt/genestack/base-helm-configs/loki/loki-helm-minio-overrides-example.yaml /etc/genestack/helm-configs/loki/loki-helm-overrides.yaml
helm upgrade --install --values /etc/genestack/helm-configs/loki/loki-helm-overrides.yaml loki grafana/loki --create-namespace --namespace grafana --version 5.47.2
echo "Sleeping for 2 minutes"
sleep 120
# /opt/genestack/bin/install-sealed-secrets.sh

echo "Installing Keystone"
/opt/genestack/bin/install-keystone.sh
echo "Deploying admin pod"
kubectl --namespace openstack apply -f /etc/genestack/manifests/utils/utils-openstack-client-admin.yaml
echo "Sleeping for 45 seconds"
sleep 45
echo "Validating Keystone"
kubectl --namespace openstack exec -ti openstack-admin-client -- openstack user list

echo "Deploy PostgreSQL Operator"
/opt/genestack/bin/install-postgres-operator.sh
sleep 10
echo "Deploy PostgreSQL Cluster"
kubectl apply -f - <<EOF
apiVersion: "acid.zalan.do/v1"
kind: postgresql
metadata:
  name: postgres-cluster
  namespace: openstack
spec:
  dockerImage: ghcr.io/zalando/spilo-16:3.2-p3
  teamId: "acid"
  numberOfInstances: 3
  postgresql:
    version: "16"
    parameters:
      shared_buffers: "2GB"
      max_connections: "1024"
      log_statement: "all"
  volume:
    size: 40Gi
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
          - key: node-role.kubernetes.io/worker
            operator: In
            values:
            - worker
EOF
echo "Sleeping for 2 minutes"
sleep 120
echo "Deploy Gnocchi"
kubectl apply -n openstack -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: ceph-etc
  namespace: openstack
data:
  ceph.conf: |
    [global]
    mon_host = $(for pod in $(kubectl get pods -n rook-ceph | grep rook-ceph-mon | awk '{print $1}'); do \
        echo -n "$(kubectl get pod $pod -n rook-ceph -o go-template --template='{{.status.podIP}}'):6789,"; done \
        | sed 's/,$//')
EOF
# Verify ceph configmap is sane
# kubectl get configmap -n openstack ceph-etc -o "jsonpath={.data['ceph\.conf']}"

/opt/genestack/bin/install-gnocchi.sh
echo "Sleeping for 3 minutes"
sleep 180
kubectl exec -it openstack-admin-client -n openstack -- /var/lib/openstack/bin/pip install python-ceilometerclient gnocchiclient

echo "Confirm healthcheck"
curl http://gnocchi-api.openstack.svc.${GATEWAY_DOMAIN}/healthcheck -D -

kubectl exec -it openstack-admin-client -n openstack -- openstack metric list --debug

echo "Deploy Ceilometer"
cat <<EOF > /etc/genestack/helm-configs/ceilometer/ceilometer-helm-overrides.yaml
images:
  tags:
    test: "quay.io/rackspace/rackerlabs-xrally-openstack:2.0.0"
    ceilometer_db_sync: "ghcr.io/lukerepko/genestack/ceilometer:2024.1-ubuntu_jammy-1739629417"
    rabbit_init: "quay.io/rackspace/rackerlabs-rabbitmq:3.13-management"
    ks_user: "quay.io/rackspace/rackerlabs-heat:2024.1-ubuntu_jammy"
    ks_service: "quay.io/rackspace/rackerlabs-heat:2024.1-ubuntu_jammy"
    ceilometer_central: "ghcr.io/lukerepko/genestack/ceilometer:2024.1-ubuntu_jammy-1739629417"
    ceilometer_compute: "ghcr.io/lukerepko/genestack/ceilometer:2024.1-ubuntu_jammy-1739629417"
    ceilometer_ipmi: "ghcr.io/lukerepko/genestack/ceilometer:2024.1-ubuntu_jammy-1739629417"
    ceilometer_notification: "ghcr.io/lukerepko/genestack/ceilometer:2024.1-ubuntu_jammy-1739629417"
    dep_check: "quay.io/rackspace/rackerlabs-kubernetes-entrypoint:v1.0.0"
    image_repo_sync: "quay.io/rackspace/rackerlabs-docker:17.07.0"
  pull_policy: "Always"


conf:
  ceilometer:
    DEFAULT:
      debug: "true"
      default_log_levels: >-
        amqp=WARN,amqplib=WARN,boto=WARN,qpid=WARN,sqlalchemy=WARN,suds=INFO,oslo.messaging=INFO,
        oslo_messaging=INFO,iso8601=WARN,requests.packages.urllib3.connectionpool=DEBUG,
        urllib3.connectionpool=DEBUG,websocket=WARN,requests.packages.urllib3.util.retry=DEBUG,
        urllib3.util.retry=DEBUG,keystonemiddleware=WARN,routes.middleware=WARN,stevedore=WARN,
        taskflow=WARN,keystoneauth=WARN,oslo.cache=INFO,oslo_policy=INFO,dogpile.core.dogpile=INFO
        
  event_definitions:
    - event_type:
        [
          "network.*",
          "subnet.*",
          "port.*",
          "router.*",
          "floatingip.*",
          "firewall.*",
          "firewall_policy.*",
          "firewall_rule.*",
          "vpnservice.*",
          "ipsecpolicy.*",
          "ikepolicy.*",
          "ipsec_site_connection.*",
          "l3.*",
        ]
      traits: &network_traits
        user_id:
          fields: ctxt.user_id
        project_id:
          fields: ctxt.tenant_id

EOF
/opt/genestack/bin/install-ceilometer.sh
echo "Sleeping for 2 minutes"
sleep 120
echo "Installing Glance"
/opt/genestack/bin/install-glance.sh
echo "Sleeping for 1 minute"
sleep 60
echo "Validating Glance"
kubectl --namespace openstack exec -ti openstack-admin-client -- openstack image list
echo "Installing Heat"
/opt/genestack/bin/install-heat.sh
echo "Sleeping for 30 seconds"
sleep 30
# echo "Validating Heat"
# kubectl --namespace openstack exec -ti openstack-admin-client -- openstack --os-interface internal orchestration service list
echo "Installing Cinder"
/opt/genestack/bin/install-cinder.sh
echo "Sleeping for 45 seconds"
sleep 45
echo "Installing Cinder LVM iSCSI"
echo -e "Attach the cinder volumes to each storage node, and log into them and run the following commands:\nsudo pvcreate /dev/vd[def]\nsudo vgcreate cinder-volumes-1 /dev/vd[def]."
read -rp "Press enter to continue when done. "
echo "Deploy Cinder Volume"
# sudo pvcreate /dev/vd[ghi]  
# sudo vgcreate cinder-volumes-1 /dev/vd[ghi]
# $lsblk -f
 # ansible-playbook /opt/genestack/ansible/playbooks/deploy-cinder-volumes-reference.yaml --limit storage03.cluster.local -e cinder_storage_network_interface=ansible_enp4s0
for node in storage0{1..3}.cluster.local;do ansible-playbook /opt/genestack/ansible/playbooks/deploy-cinder-volumes-reference.yaml --limit $node -e cinder_storage_network_interface=ansible_enp4s0;done
echo "Sleeping for 45 seconds"
sleep 45
kubectl --namespace openstack exec -ti openstack-admin-client -- openstack volume service list

kubectl --namespace openstack exec -ti openstack-admin-client -- openstack volume type create lvmdriver-1

echo "Deploy Placement"
/opt/genestack/bin/install-placement.sh
echo "Sleeping for 45 seconds"
sleep 45
cat <<'EOF'>> /etc/genestack/helm-configs/nova/nova-helm-overrides.yaml
conf:
  nova:
    conductor:
      workers: 2
    schedule:
      workers: 2
EOF
echo "Deploy Nova"
/opt/genestack/bin/install-nova.sh
echo "Deploy Neutron"
cat <<'EOF' > /etc/genestack/helm-configs/neutron/neutron-helm-overrides.yaml
conf:
  neutron:
    DEFAULT:
      global_physnet_mtu: 9000
  plugins:
    ml2_conf:
      ml2:
        path_mtu: 4000
        physical_network_mtus: physnet1:1500
EOF
/opt/genestack/bin/install-neutron.sh
echo "Sleeping for 3 minutes"
sleep 180

echo "Creating Openstack Cloud Config"
mkdir -p ~/.config/openstack
sudo apt install python3-keyring -y
cat >  ~/.config/openstack/clouds.yaml <<EOF
cache:
  auth: true
  expiration_time: 3600
clouds:
  default:
    auth:
      auth_url: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_AUTH_URL}' | base64 -d)
      project_name: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_PROJECT_NAME}' | base64 -d)
      tenant_name: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_USER_DOMAIN_NAME}' | base64 -d)
      project_domain_name: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_PROJECT_DOMAIN_NAME}' | base64 -d)
      username: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_USERNAME}' | base64 -d)
      password: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_PASSWORD}' | base64 -d)
      user_domain_name: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_USER_DOMAIN_NAME}' | base64 -d)
    region_name: $(kubectl --namespace openstack get secret keystone-keystone-admin -o jsonpath='{.data.OS_REGION_NAME}' | base64 -d)
    interface: public
    identity_api_version: "3"
EOF
find ~/.config/openstack/clouds.yaml -type f -exec sed -i "s/keystone-api.openstack.svc.cluster.local:5000/keystone.${GATEWAY_DOMAIN}/g" {} +

echo "Deploying Skyline"
kubectl --namespace openstack apply -k /etc/genestack/kustomize/skyline/overlay
