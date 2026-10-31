pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
    }

    environment {
        IMAGE  = 'kaching437/daybook'
        TAG    = "${env.BUILD_NUMBER}"
        DOCKER = credentials('dockerhub-creds')   // exposes DOCKER_USR and DOCKER_PSW
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Test') {
            steps {
                bat '''
                python -m venv .venv || exit /b 1
                .venv\\Scripts\\python -m pip install -q -r requirements-dev.txt || exit /b 1
                .venv\\Scripts\\python -m pytest -q || exit /b 1
                '''
            }
        }

        stage('Build image') {
            steps {
                bat 'docker build -t %IMAGE%:%TAG% --build-arg APP_VERSION=%TAG% .'
            }
        }

        stage('Push image') {
            steps {
                bat '''
                set DOCKER_CONFIG=%WORKSPACE%\\.docker
                echo %DOCKER_PSW%| docker login -u %DOCKER_USR% --password-stdin || exit /b 1
                docker push %IMAGE%:%TAG% || exit /b 1
                docker logout
                '''
            }
        }

        stage('Deploy') {
            steps {
                powershell '''
                kubectl apply -f k8s/pvc.yaml -f k8s/service.yaml
                if ($LASTEXITCODE -ne 0) { exit 1 }

                (Get-Content k8s/deployment.yaml) -replace 'image: kaching437/daybook:\\S+', "image: ${env:IMAGE}:${env:TAG}" | kubectl apply -f -
                if ($LASTEXITCODE -ne 0) { exit 1 }

                kubectl rollout status deployment/daybook --timeout=120s
                if ($LASTEXITCODE -ne 0) { exit 1 }
                '''
            }
        }
    }
}