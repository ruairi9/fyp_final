JENKINS_ADMIN_PASSWORD = "admin123"
HOST_IP = "192.168.2.49"

RUN_PIPELINE = <<-'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Build')   { steps { echo 'Building...';  sleep 8 } }
        stage('Test')    { steps { echo 'Testing...';   sleep 5 } }
        stage('Deploy')  { steps { echo 'Deploying...'; sleep 10 } }
    }
    post {
        success { echo 'Done' }
        failure { echo 'Failed' }
    }
}
PIPELINE

DEMO_PIPELINE = <<-'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Checkout') { steps { echo 'Pulling code...'; sleep 3 } }
        stage('Build')    { steps { echo 'Compiling...';    sleep 7 } }
        stage('Test')     { steps { echo 'Running tests...'; sleep 5 } }
        stage('Push')     { steps { echo 'Pushing image...'; sleep 4 } }
    }
}
PIPELINE

HEALTH_CHECK_PIPELINE = <<-'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Check VMs')     { steps { echo 'Pinging VMs...';     sleep 10 } }
        stage('Check K8s')     { steps { echo 'Checking nodes...';  sleep 5 } }
        stage('Check Services'){ steps { echo 'Hitting endpoints...'; sleep 8 } }
    }
    post {
        failure { echo 'Something is down' }
    }
}
PIPELINE

NGINX_PIPELINE = <<-'PIPELINE'
pipeline {
    agent { label 'host-agent' }
    environment {
        KUBECONFIG    = '/home/vagrant/k3s.yaml'
        APP_NAME      = 'sdos-nginx'
        DEV_NAMESPACE = 'development'
        PRD_NAMESPACE = 'production'
    }
    stages {
        stage('Build') {
            steps {
                echo 'Creating nginx Kubernetes manifests...'
                sh '''
                    mkdir -p /tmp/sdos-nginx
                    cat > /tmp/sdos-nginx/dev-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sdos-nginx-dev
  namespace: development
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sdos-nginx
      env: development
  template:
    metadata:
      labels:
        app: sdos-nginx
        env: development
    spec:
      nodeSelector:
        node-role: integration
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: sdos-nginx-dev
  namespace: development
spec:
  type: NodePort
  selector:
    app: sdos-nginx
    env: development
  ports:
  - port: 80
    targetPort: 80
    nodePort: 30081
EOF
                    cat > /tmp/sdos-nginx/prod-deployment.yaml <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sdos-nginx-prod
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sdos-nginx
      env: production
  template:
    metadata:
      labels:
        app: sdos-nginx
        env: production
    spec:
      nodeSelector:
        node-role: security-testing
      containers:
      - name: nginx
        image: nginx:alpine
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: sdos-nginx-prod
  namespace: production
spec:
  type: NodePort
  selector:
    app: sdos-nginx
    env: production
  ports:
  - port: 80
    targetPort: 80
    nodePort: 30082
EOF
                    echo "Manifests created"
                '''
            }
        }
        stage('Test') {
            steps {
                sh '''
                    kubectl --kubeconfig=$KUBECONFIG create namespace development --dry-run=client -o yaml | kubectl --kubeconfig=$KUBECONFIG apply -f -
                    kubectl --kubeconfig=$KUBECONFIG apply -f /tmp/sdos-nginx/dev-deployment.yaml
                    kubectl --kubeconfig=$KUBECONFIG rollout status deployment/sdos-nginx-dev -n development --timeout=120s
                    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.20:30081 --connect-timeout 10 || echo "000")
                    echo "Dev HTTP: $HTTP_CODE"
                '''
            }
        }
        stage('Staging') {
            steps {
                sh '''
                    PASS=0; FAIL=0
                    CODE=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.20:30081 --connect-timeout 10 || echo "000")
                    [ "$CODE" = "200" ] && PASS=$((PASS+1)) && echo "PASS: HTTP 200" || { FAIL=$((FAIL+1)); echo "FAIL: HTTP $CODE"; }
                    echo "Tests: $PASS passed, $FAIL failed"
                '''
            }
        }
        stage('Load') {
            steps {
                sh '''
                    SUCCESS=0; FAIL=0
                    for i in $(seq 1 50); do
                        CODE=$(curl -s -o /dev/null -w "%{http_code}" http://192.168.121.20:30081 --connect-timeout 5 || echo "000")
                        [ "$CODE" = "200" ] && SUCCESS=$((SUCCESS+1)) || FAIL=$((FAIL+1))
                    done
                    echo "Load test: $SUCCESS/50 successful"
                    [ "$SUCCESS" -lt "40" ] && exit 1 || echo "PASS"
                '''
            }
        }
        stage('Production') {
            steps {
                sh '''
                    kubectl --kubeconfig=$KUBECONFIG create namespace production --dry-run=client -o yaml | kubectl --kubeconfig=$KUBECONFIG apply -f -
                    kubectl --kubeconfig=$KUBECONFIG apply -f /tmp/sdos-nginx/prod-deployment.yaml
                    kubectl --kubeconfig=$KUBECONFIG rollout status deployment/sdos-nginx-prod -n production --timeout=120s
                    echo "Dev:        http://192.168.121.20:30081"
                    echo "Production: http://192.168.121.30:30082"
                '''
            }
        }
    }
    post {
        always { sh 'rm -rf /tmp/sdos-nginx || true' }
        success { echo 'nginx deployed to dev and production!' }
        failure {
            sh '''
                kubectl --kubeconfig=$KUBECONFIG delete deployment sdos-nginx-dev  -n development --ignore-not-found=true || true
                kubectl --kubeconfig=$KUBECONFIG delete deployment sdos-nginx-prod -n production  --ignore-not-found=true || true
            '''
        }
    }
}
PIPELINE

Vagrant.configure("2") do |config|
  config.vm.box = "generic/ubuntu2204"
  config.vm.box_check_update = false

  config.vm.define "control-plane" do |control|
    control.vm.hostname = "control-plane"
    control.vm.network "private_network", ip: "192.168.121.10"

    control.vm.provider "libvirt" do |lv|
      lv.memory = "2048"
      lv.cpus = 2
      lv.driver = "kvm"
    end

    control.vm.provision "shell", inline: <<-SHELL
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" sh -s - server \
        --node-name control-plane \
        --disable traefik \
        --disable servicelb \
        --bind-address=0.0.0.0 \
        --advertise-address=192.168.121.10 \
        --node-taint node-role.kubernetes.io/control-plane:NoSchedule \
        --node-label="node-role=control-plane" \
        --tls-san=192.168.121.10 \
        --tls-san=control-plane
      sleep 10
      sudo cat /var/lib/rancher/k3s/server/node-token > /vagrant/k3s-token.txt
      sudo cat /etc/rancher/k3s/k3s.yaml > /vagrant/k3s.yaml
      sudo sed -i 's/127.0.0.1/192.168.121.10/g' /vagrant/k3s.yaml
      echo "Control Plane Ready!"
      kubectl get nodes
    SHELL
  end

  config.vm.define "worker-dev" do |worker|
    worker.vm.hostname = "worker-dev-integration"
    worker.vm.network "private_network", ip: "192.168.121.20"

    worker.vm.provider "libvirt" do |lv|
      lv.memory = "2048"
      lv.cpus = 2
      lv.driver = "kvm"
    end

    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-dev-integration \
        --node-label="node-role=development" \
        --node-label="node-role=integration" \
        --node-label="environment=dev"
      echo "Development Worker Ready!"
    SHELL
  end

  config.vm.define "worker-prod" do |worker|
    worker.vm.hostname = "worker-production"
    worker.vm.network "private_network", ip: "192.168.121.30"

    worker.vm.provider "libvirt" do |lv|
      lv.memory = "4096"
      lv.cpus = 2
      lv.driver = "kvm"
    end

    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-production \
        --node-label="node-role=production" \
        --node-label="node-role=load-testing" \
        --node-label="node-role=security-testing" \
        --node-label="environment=prod"
      echo "Production Worker Ready!"
    SHELL
  end

  config.vm.define "worker-cicd" do |worker|
    worker.vm.hostname = "worker-cicd"
    worker.vm.network "private_network", ip: "192.168.121.40"
    worker.vm.network "forwarded_port", guest: 32080, host: 32080

    worker.vm.provider "libvirt" do |lv|
      lv.memory = "4096"
      lv.cpus = 3
      lv.driver = "kvm"
    end

    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done

      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-cicd \
        --node-label="node-role=cicd" \
        --node-label="environment=cicd"

      curl -fsSL https://get.docker.com | sudo sh
      sudo usermod -aG docker vagrant

      sudo docker run -d \
        --name jenkins \
        --restart unless-stopped \
        -p 32080:8080 \
        -p 50000:50000 \
        -v jenkins_home:/var/jenkins_home \
        jenkins/jenkins:lts

      echo "Waiting for Jenkins to start..."
      until sudo docker exec jenkins curl -s http://localhost:8080/login > /dev/null 2>&1; do
        echo "Jenkins starting..."
        sleep 10
      done
      sleep 20
      echo "Jenkins is up"

      INIT_PASS=$(sudo docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword)
      echo "Initial password: $INIT_PASS"

      sudo docker exec jenkins curl -s http://localhost:8080/jnlpJars/jenkins-cli.jar -o /tmp/jenkins-cli.jar

      sudo docker exec jenkins java -jar /tmp/jenkins-cli.jar \
        -s http://localhost:8080 \
        -auth admin:$INIT_PASS \
        install-plugin \
          workflow-aggregator \
          git \
          ssh-slaves \
          pipeline-stage-view \
          credentials \
          ssh-credentials \
          matrix-auth \
          --restart || true

      echo "Waiting for Jenkins to restart after plugins..."
      sleep 60
      until sudo docker exec jenkins curl -s http://localhost:8080/login > /dev/null 2>&1; do
        echo "Jenkins restarting..."
        sleep 10
      done

      sudo docker exec jenkins bash -c "cat > /tmp/create-admin.groovy << 'EOF'
import jenkins.model.*
import hudson.security.*
import jenkins.install.*

def instance = Jenkins.getInstance()

instance.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)

def hudsonRealm = new HudsonPrivateSecurityRealm(false)
hudsonRealm.createAccount('admin', '#{JENKINS_ADMIN_PASSWORD}')
instance.setSecurityRealm(hudsonRealm)

def strategy = new FullControlOnceLoggedInAuthorizationStrategy()
strategy.setAllowAnonymousRead(false)
instance.setAuthorizationStrategy(strategy)

instance.save()
EOF
"
      sudo docker exec jenkins java -jar /tmp/jenkins-cli.jar \
        -s http://localhost:8080 \
        -auth admin:$INIT_PASS \
        groovy = < /tmp/create-admin.groovy || true

      sleep 10

      echo "Jenkins URL:      http://192.168.121.40:32080" > /vagrant/jenkins-info.txt
      echo "Username:         admin" >> /vagrant/jenkins-info.txt
      echo "Password:         #{JENKINS_ADMIN_PASSWORD}" >> /vagrant/jenkins-info.txt
      echo "Initial password: $INIT_PASS" >> /vagrant/jenkins-info.txt

      echo "CI/CD Worker Ready Jenkins running at http://192.168.121.40:32080"
    SHELL

    worker.vm.provision "shell", inline: <<-CREATEJOBS
      JENKINS_URL="http://localhost:32080"
      AUTH="admin:#{JENKINS_ADMIN_PASSWORD}"

      until curl -s -u $AUTH $JENKINS_URL/api/json > /dev/null 2>&1; do
        echo "Waiting for Jenkins API..."
        sleep 10
      done
      echo "Jenkins API ready"

      CRUMB=$(curl -s -u $AUTH "$JENKINS_URL/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)" 2>/dev/null || echo "")

      create_job() {
        JOB_NAME=$1
        PIPELINE_SCRIPT=$2
        ESCAPED=$(echo "$PIPELINE_SCRIPT" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g')
        XML="<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin='workflow-job'>
  <description></description>
  <keepDependencies>false</keepDependencies>
  <definition class='org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition' plugin='workflow-cps'>
    <script>${ESCAPED}</script>
    <sandbox>true</sandbox>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>"
        if [ -n "$CRUMB" ]; then
          curl -s -u $AUTH -H "$CRUMB" -H "Content-Type: application/xml" \
            -d "$XML" "$JENKINS_URL/createItem?name=$JOB_NAME" > /dev/null
        else
          curl -s -u $AUTH -H "Content-Type: application/xml" \
            -d "$XML" "$JENKINS_URL/createItem?name=$JOB_NAME" > /dev/null
        fi
        echo "Created pipeline: $JOB_NAME"
      }

      create_job "run" "pipeline { agent any stages { stage('Build') { steps { echo 'Building...'; sleep 6 } } stage('Test') { steps { echo 'Testing...'; sleep 6 } } stage('Staging') { steps { echo 'Staging...'; sleep 6 } } stage('Load') { steps { echo 'Load testing...'; sleep 6 } } stage('Production') { steps { echo 'Deploying...'; sleep 6 } } } }"

      create_job "demo-pipeline" "pipeline { agent any stages { stage('Build') { steps { echo 'Building demo...'; sleep 6 } } stage('Test') { steps { echo 'Testing demo...'; sleep 6 } } stage('Staging') { steps { echo 'Staging demo...'; sleep 6 } } stage('Load') { steps { echo 'Load testing...'; sleep 6 } } stage('Production') { steps { echo 'Deploying demo...'; sleep 6 } } } }"

      create_job "health-check" "pipeline { agent any stages { stage('Build') { steps { echo 'Starting health check...'; sleep 6 } } stage('Test') { steps { echo 'Checking services...'; sleep 6 } } stage('Staging') { steps { echo 'Checking staging...'; sleep 6 } } stage('Load') { steps { echo 'Checking load...'; sleep 6 } } stage('Production') { steps { echo 'All systems healthy!'; sleep 6 } } } }"

      create_job "hello-world" "pipeline { agent any stages { stage('Hello') { steps { echo 'Hello World from SDOS!' } } stage('Test') { steps { echo 'All tests passed!'; sleep 6 } } } }"


      if [ -f /vagrant/Jenkinsfiles/safe-load-test ]; then
        LOAD_SCRIPT=$(cat /vagrant/Jenkinsfiles/safe-load-test)
        create_job "safe-load-test" "$LOAD_SCRIPT"
      else
        echo "WARNING: safe-load-test Jenkinsfile not found in repo"
      fi

      if [ -f /vagrant/Jenkinsfiles/nginx-deploy ]; then
        NGINX_SCRIPT=$(cat /vagrant/Jenkinsfiles/nginx-deploy)
        create_job "nginx-deploy" "$NGINX_SCRIPT"
      else
        echo "WARNING: nginx-deploy Jenkinsfile not found in repo"
      fi
      echo "All pipelines created"

      sudo -u vagrant ssh-keygen -t ed25519 -f /home/vagrant/.ssh/jenkins_agent -N "" -q 2>/dev/null || true
      PUB_KEY=$(cat /home/vagrant/.ssh/jenkins_agent.pub 2>/dev/null || echo "")
      PRIV_KEY=$(cat /home/vagrant/.ssh/jenkins_agent 2>/dev/null || echo "")

      echo "$PUB_KEY" > /vagrant/jenkins_agent.pub
      echo "$PRIV_KEY" > /vagrant/jenkins_agent.key
      chmod 600 /vagrant/jenkins_agent.key

      sudo docker exec jenkins bash -c "cat > /tmp/add-ssh-cred.groovy << 'GROOVY'
import com.cloudbees.jenkins.plugins.sshcredentials.impl.*
import com.cloudbees.plugins.credentials.*
import com.cloudbees.plugins.credentials.domains.*
import jenkins.model.Jenkins

def privateKey = new BasicSSHUserPrivateKey.DirectEntryPrivateKeySource('''${PRIV_KEY}''')
def credential = new BasicSSHUserPrivateKey(
    CredentialsScope.GLOBAL,
    'host-ssh-key',
    'ruairi',
    privateKey,
    '',
    'Host agent SSH key'
)
def store = Jenkins.instance.getExtensionList('com.cloudbees.plugins.credentials.SystemCredentialsProvider')[0].getStore()
store.addCredentials(Domain.global(), credential)
Jenkins.instance.save()
println 'SSH credential added'
GROOVY
" 2>/dev/null || true

      NODE_XML="<?xml version='1.1' encoding='UTF-8'?>
<slave>
  <name>host-agent</name>
  <description>Host machine agent</description>
  <remoteFS>/home/ruairi/jenkins-agent</remoteFS>
  <numExecutors>2</numExecutors>
  <mode>NORMAL</mode>
  <retentionStrategy class='hudson.slaves.RetentionStrategy\$Always'/>
  <launcher class='hudson.plugins.sshslaves.SSHLauncher' plugin='ssh-slaves'>
    <host>#{HOST_IP}</host>
    <port>22</port>
    <credentialsId>host-ssh-key</credentialsId>
    <sshHostKeyVerificationStrategy class='hudson.plugins.sshslaves.verifiers.NonVerifyingKeyVerificationStrategy'/>
  </launcher>
  <label>host-agent</label>
  <nodeProperties/>
</slave>"

      if [ -n "$CRUMB" ]; then
        curl -s -u $AUTH -H "$CRUMB" -H "Content-Type: application/xml" \
          -d "$NODE_XML" "$JENKINS_URL/computer/doCreateItem?name=host-agent&type=hudson.slaves.DumbSlave" > /dev/null || true
      else
        curl -s -u $AUTH -H "Content-Type: application/xml" \
          -d "$NODE_XML" "$JENKINS_URL/computer/doCreateItem?name=host-agent&type=hudson.slaves.DumbSlave" > /dev/null || true
      fi
      echo "host-agent node created"

      echo "======================================"
      echo "Jenkins fully configured!"
      echo "URL:      http://192.168.121.40:32080"
      echo "Username: admin"
      echo "Password: #{JENKINS_ADMIN_PASSWORD}"
      echo "======================================"
    CREATEJOBS
  end

  config.vm.define "worker-monitoring" do |worker|
    worker.vm.hostname = "worker-registry-monitoring"
    worker.vm.network "private_network", ip: "192.168.121.50"
    worker.vm.network "forwarded_port", guest: 5000,  host: 5000
    worker.vm.network "forwarded_port", guest: 30030, host: 30030
    worker.vm.network "forwarded_port", guest: 30090, host: 30090

    worker.vm.provider "libvirt" do |lv|
      lv.memory = "3072"
      lv.cpus = 2
      lv.driver = "kvm"
    end

    worker.vm.provision "shell", inline: <<-SHELL
      until [ -f /vagrant/k3s-token.txt ]; do
        echo "Waiting for control plane..."
        sleep 5
      done
      K3S_TOKEN=$(cat /vagrant/k3s-token.txt)
      curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="v1.28.5+k3s1" K3S_URL=https://192.168.121.10:6443 K3S_TOKEN=$K3S_TOKEN sh -s - agent \
        --node-name worker-registry-monitoring \
        --node-label="node-role=registry-monitoring" \
        --node-label="environment=monitoring"
      echo "Registry & Monitoring Worker Ready!"
      echo ""
      echo "========================================="
      echo "FYP 5-Server Cluster Setup Complete!"
      echo "========================================="
      echo "Control Plane:  192.168.121.10"
      echo "Worker Dev:     192.168.121.20"
      echo "Worker Prod:    192.168.121.30"
      echo "Worker CI/CD:   192.168.121.40  (Jenkins: :32080)"
      echo "Worker Monitor: 192.168.121.50  (Grafana: :32030)"
      echo ""
      echo "Jenkins login saved to: ./jenkins-info.txt"
      echo "export KUBECONFIG=./k3s.yaml"
      echo "kubectl get nodes"
    SHELL
  end
end
