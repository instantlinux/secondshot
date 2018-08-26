// Pipeline for python package / docker-image build
//  created by richb@instantlinux.net 14-aug-2018

node('swarm') {
    def buildDate = java.time.Instant.now().toString()
    def maintainer = 'docker@instantlinux.net'
    def coberturaPublish = [
        $class: 'CoberturaPublisher', autoUpdateHealth: false,
        autoUpdateStability: false, coberturaReportFile: '**/coverage.xml',
        failUnhealthy: true, failUnstable: false,
        lineCoverageTargets: '80, 70, 60', maxNumberOfBuilds: 0,
        onlyStable: false, sourceEncoding: 'UTF_8', zoomCoverageChart: false]
    def coverageOpts = [
        allowMissing: true, alwaysLinkToLastBuild: false, keepAll: true,
        reportDir: '**/htmlcov', reportFiles: 'index.html',
        reportName: 'Pytest Coverage']
    def imageTag = null
    def localCACreds = file(
        credentialsId: 'local-root-ca', variable: 'SSL_CHAIN')
    def pypiLocalCreds = [$class: 'UsernamePasswordMultiBinding',
                          credentialsId: 'pypi-local',
                          usernameVariable: 'PYPI_USER',
                          passwordVariable: 'PYPI_PASSWORD']
    def registry = 'nexus.instantlinux.net'
    def registryCreds = [credentialsId: 'docker-registry',
                         url: "https://${registry}"]
    def service = env.JOB_NAME.split('/', 2)[0]

    try {
        stage('Static Code Analysis') {
            checkout scm
            sh 'make analysis'
        }
        stage('Unit Tests') {
            sh 'make test'
            junit '**/*.xml'
            step(coberturaPublish)
            publishHTML target: coverageOpts
        }
        stage('Publish Package') {
            withCredentials([pypiLocalCreds, localCACreds]) {
                sh 'make publish'
            }
        }
        stage('Create Image') {
            gitCommit = checkout(scm).GIT_COMMIT
            imageTag = "dev_build_${env.BUILD_NUMBER}_${gitCommit.take(7)}"
            img = docker.build("${registry}/${service}:${imageTag}",
                               "--build-arg=VCS_REF=${gitCommit} " +
                               "--build-arg=BUILD_DATE=${buildDate} .")
        }
        stage('Push Image') {
            withDockerRegistry(registryCreds) {
                img.push imageTag
            }
        }
        stage('Verify & Promote') {
            sh 'make test_functional'
            withDockerRegistry(registryCreds) {
                img.push 'latest'
            }
        }
    }
    catch (Exception ex) {
        echo "Exception caught: ${ex.getMessage()}"
        currentBuild.result = 'FAILURE'
    }
    finally {
        currentBuild.result = currentBuild.result ?: 'SUCCESS'
        emailext (
            to: maintainer,
            subject: "Job ${env.JOB_NAME} #${env.BUILD_NUMBER} ${currentBuild.result}",
            body: "Build URL: ${env.BUILD_URL}.\nDocker Image ${registry}/${service}\n",
            attachLog: true
        )
        stage('Clean') {
            if (imageTag) {
                sh "docker rmi ${registry}/${service}:${imageTag}"
            }
            deleteDir()
        }
    }
}
