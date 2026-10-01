{{/*
============================================================
Qurilish Korxonasi — Helm Template Helpers
============================================================
*/}}

{{/* App name */}}
{{- define "qurilish.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Full name */}}
{{- define "qurilish.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/* Chart label */}}
{{- define "qurilish.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/* Common labels */}}
{{- define "qurilish.labels" -}}
helm.sh/chart: {{ include "qurilish.chart" . }}
{{ include "qurilish.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: qurilish-factory
{{- end }}

{{/* Selector labels */}}
{{- define "qurilish.selectorLabels" -}}
app.kubernetes.io/name: {{ include "qurilish.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/* Image name */}}
{{- define "qurilish.image" -}}
{{- $tag := .tag | default $.global.imageTag | default "latest" -}}
{{- printf "%s/%s:%s" $.global.imageRegistry .repository $tag -}}
{{- end }}
