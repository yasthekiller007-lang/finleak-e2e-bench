-- Disposable finleak_product_v11_test only. Apply after migrations and source-only seed.
-- The application does not own the database, schema, tables, or migration role.
REVOKE ALL ON DATABASE finleak_product_v11_test FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE finleak_product_v11_test TO finleak_p0;
GRANT USAGE ON SCHEMA public TO finleak_p0;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO finleak_p0;
GRANT INSERT ON reviewed_financial_sources, financial_revisions, financial_revision_evidence,
  financial_evaluations, financial_finding_decisions, financial_audit,
  proof_families, proof_packages, proof_bindings, proof_events, proof_artifacts,
  proof_requests, proof_successors TO finleak_p0;
-- PostgreSQL SELECT FOR UPDATE/SHARE needs UPDATE privilege on at least one column.
-- No grant to update membership roles, decisions, audit reasons or financial values.
DO $$
DECLARE item RECORD;
BEGIN
  FOR item IN SELECT table_name FROM information_schema.columns
    WHERE table_schema='public' AND column_name='id'
  LOOP
    EXECUTE format('GRANT UPDATE(id) ON TABLE public.%I TO finleak_p0', item.table_name);
  END LOOP;
END $$;
