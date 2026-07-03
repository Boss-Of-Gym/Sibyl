{{- define "sibyl.labels" -}}
app.kubernetes.io/name: sibyl
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "sibyl.apiLabels" -}}
{{ include "sibyl.labels" . }}
app.kubernetes.io/component: api
{{- end -}}

{{- define "sibyl.workerLabels" -}}
{{ include "sibyl.labels" . }}
app.kubernetes.io/component: worker
{{- end -}}
