pypiLocalCreds = [[$class: 'UsernamePasswordMultiBinding',
                   credentialsId: 'pypi-local',
                   usernameVariable: 'PYPI_USER',
                   passwordVariable: 'PYPI_PASSWOR']]
pipeline {
  agent { label 'swarm' }
  stages {
    stage('Static Code Analysis') {
      steps {
        sh "make analysis"
      }
    }
    stage('Unit Tests') {
      steps {
	sh "make test"
        junit '**/*.xml'
      }
    }
    stage('Publish Package') {
      steps {
        withCredentials(pypiLocalCreds) {
	  script {
	    sh "make publish"
          }
        }
      }
    }
    stage('Create Image') {
      steps {
	script {
	  img = docker.build "${registry}/${env.JOB_NAME}:build_${env.BUILD_NUMBER}"
	}
      }
    }
    stage('Push Image') {
      steps {
	script {
	  img.push "build_$env.BUILD_NUMBER"
	}
      }
    }
    stage('Functional Tests') {
      steps {
	sh "make test_functional"
	script {
	  img.push "latest"
	}
      }
    }
  }
  post {
    always {
      deleteDir()
    }
    success {
      emailext (
	to: 'richb@pioneer.ci.net',
	subject: "Job ${env.JOB_NAME} #${env.BUILD_NUMBER} success",
	body: "Build URL: ${env.BUILD_URL}.\n",
	attachLog: true
      )
    }
    failure {
      sh "docker rmi ${registry}/${env.JOB_NAME}:build_${env.BUILD_NUMBER}"
      emailext (
	to: 'richb@pioneer.ci.net',
	subject: "Job ${env.JOB_NAME} #${env.BUILD_NUMBER} failed",
	body: "Failed build URL: ${env.BUILD_URL}.\n",
	attachLog: true
      )
    }
  }
}
