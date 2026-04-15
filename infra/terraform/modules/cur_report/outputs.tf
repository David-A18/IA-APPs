output "report_name" {
  description = "Name of the CUR report definition"
  value       = aws_cur_report_definition.this.report_name
}

output "report_arn" {
  description = "ARN of the CUR report definition"
  value       = aws_cur_report_definition.this.arn
}
