#!/bin/bash

echo "Creating Jenkins Test Pipelines..."

# TC1 - Manual Trigger
cat > TC1-manual-trigger.jenkins <<'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Manual Test') {
            steps {
                echo 'TC1: Manual trigger test'
                sh 'date'
            }
        }
    }
}
PIPELINE

# TC4 - Successful Build
cat > TC4-successful-build.jenkins <<'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Building application...'
                sh 'echo "Build successful"'
            }
        }
        stage('Test') {
            steps {
                echo 'Running tests...'
                sh 'exit 0'
            }
        }
    }
}
PIPELINE

# TC5 - Failed Build  
cat > TC5-failed-build.jenkins <<'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'This will fail...'
                sh 'exit 1'
            }
        }
    }
}
PIPELINE

# TC9 - Parallel Stages
cat > TC9-parallel-stages.jenkins <<'PIPELINE'
pipeline {
    agent any
    stages {
        stage('Parallel Execution') {
            parallel {
                stage('Branch A') {
                    steps {
                        echo 'Running parallel branch A'
                        sleep 5
                        echo 'Branch A complete'
                    }
                }
                stage('Branch B') {
                    steps {
                        echo 'Running parallel branch B'
                        sleep 5
                        echo 'Branch B complete'
                    }
                }
            }
        }
    }
}
PIPELINE

echo "✅ Test pipeline files created!"
ls -1 *.jenkins
