-- Curated synthetic records for public research acceptance. They are test
-- fixtures, not evidence that manually created draft entities are published.
BEGIN;
INSERT INTO entities (
  id, tenant_id, entity_type, name, normalized_name, description,
  external_ids, attributes, review_status, created_at, updated_at
) VALUES (
  :'target_id', :'tenant_id', 'TARGET', :'target_name', lower(:'target_name'),
  'Synthetic curated browser research fixture',
  jsonb_build_object('acceptance', :'fixture_key'),
  jsonb_build_object('acceptance_fixture', true, 'acceptance_fixture_key', :'fixture_key', 'organism', 'Homo sapiens'),
  'VERIFIED', now(), now()
), (
  :'company_id', :'tenant_id', 'ORGANIZATION', :'company_name', lower(:'company_name'),
  'Synthetic curated browser company fixture',
  jsonb_build_object('acceptance', :'fixture_key' || '-company'),
  jsonb_build_object('acceptance_fixture', true, 'acceptance_fixture_key', :'fixture_key'),
  'VERIFIED', now(), now()
);
COMMIT;
