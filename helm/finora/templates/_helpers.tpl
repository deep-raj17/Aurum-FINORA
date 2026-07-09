{{- define "finora.name" -}}finora{{- end }}
{{- define "finora.labels" -}}
app.kubernetes.io/name: {{ include "finora.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
