-- Phase 1F.1 MIS Manager RLS policy blocks

ALTER TABLE mis_template_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_template_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_template_versions_tenant_isolation
  ON mis_template_versions
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_template_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_template_sections FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_template_sections_tenant_isolation
  ON mis_template_sections
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_template_columns ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_template_columns FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_template_columns_tenant_isolation
  ON mis_template_columns
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_template_row_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_template_row_mappings FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_template_row_mappings_tenant_isolation
  ON mis_template_row_mappings
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_data_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_data_snapshots FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_data_snapshots_tenant_isolation
  ON mis_data_snapshots
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_normalized_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_normalized_lines FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_normalized_lines_tenant_isolation
  ON mis_normalized_lines
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_ingestion_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_ingestion_exceptions FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_ingestion_exceptions_tenant_isolation
  ON mis_ingestion_exceptions
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_drift_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_drift_events FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_drift_events_tenant_isolation
  ON mis_drift_events
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_canonical_metric_dictionary ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_canonical_metric_dictionary FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_canonical_metric_dictionary_tenant_isolation
  ON mis_canonical_metric_dictionary
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

ALTER TABLE mis_canonical_dimension_dictionary ENABLE ROW LEVEL SECURITY;
ALTER TABLE mis_canonical_dimension_dictionary FORCE ROW LEVEL SECURITY;
CREATE POLICY mis_canonical_dimension_dictionary_tenant_isolation
  ON mis_canonical_dimension_dictionary
  USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
