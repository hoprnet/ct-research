{{/*
Expand the name of the chart.
*/}}
{{- define "ctdapp.name" -}}
{{- default .Chart.Name .Values.ctdapp.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "ctdapp.fullname" -}}
{{- if .Values.ctdapp.fullnameOverride }}
{{- .Values.ctdapp.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.ctdapp.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ctdapp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "ctdapp.labels" -}}
helm.sh/chart: {{ include "ctdapp.chart" . }}
{{ include "ctdapp.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "ctdapp.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ctdapp.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "ctdapp.serviceAccountName" -}}
{{- if .Values.ctdapp.serviceAccount.create }}
{{- default (include "ctdapp.fullname" .) .Values.ctdapp.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.ctdapp.serviceAccount.name }}
{{- end }}
{{- end }}
