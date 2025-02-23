-- password is langfarm
insert into users(id, name, email, password) values (
	'cm6g082zk000013r2t86dhtib', 'Langfarm', 'langfarm@126.com'
	, '$2a$12$PwlfT9JPFYcnAzYCXHx1x.AgdlZwyVLeSmFmAPwkWA6VVTAYRnuMW'
)
;

insert into organizations(id, name) values ('cm6g0t2nu000113r2msztoha4', 'langfarm');

insert into organization_memberships(id, org_id, user_id, role) values (
    'cm6ok6abq0005x2j8vd9xlx4d', 'cm6g0t2nu000113r2msztoha4', 'cm6g082zk000013r2t86dhtib', 'OWNER'
);

insert into projects(id, name, org_id) values ('cm6g0uptx000613r2ha6hxtkc', 'llm-demo', 'cm6g0t2nu000113r2msztoha4');

-- LANGFUSE_SECRET_KEY=sk-lf-f69c6951-3462-4997-ba22-1c598e8308aa
-- LANGFUSE_PUBLIC_KEY=pk-lf-a82c2304-c8ee-4b24-aafc-f3d228ca336c
insert into api_keys(id, public_key, hashed_secret_key, display_secret_key, project_id, fast_hashed_secret_key) values (
    'cm6g0uzgj000913r25shr4z98', 'pk-lf-a82c2304-c8ee-4b24-aafc-f3d228ca336c'
    , '$2a$11$J6Sjn80QIyA0T1uy8V2ei.VqaiMjqH0B6dDz83xwxC0T6Mkw7awSe'
    , 'sk-lf-...08aa', 'cm6g0uptx000613r2ha6hxtkc'
    , 'ba74bf29a00183aa793040fc20dc94930e99826c40b0c85ec746688a62f04c47'
);

INSERT INTO models(
	id, created_at, updated_at, project_id, model_name, match_pattern
	, start_date, input_price, output_price, total_price, unit, tokenizer_config, tokenizer_id
) VALUES
(
	'cm3azlpbl000o3rpmuhabmi9y',now(),now(),null,'qwen-turbo','(?i)^(qwen-turbo)(-[\da-zA-Z]+)*$'
	,null,0.0000003,0.0000006,null,'TOKENS','{}',null
)
,(
	'cm3azj5o6000g3rpmnd4llx6f',now(),now(),null,'qwen-plus','(?i)^(qwen-plus)(-[\da-zA-Z]+)*$'
	,null,0.0000016,0.000004,null,'TOKENS','{}',null
)
,(
	'cm3azj5o6000g3rpmxb3iiu8g',now(),now(),null,'qwen-plus','(?i)^(qwen-plus)(-[\da-zA-Z]+)*$'
	,'2024-10-01',0.0000008,0.000002,null,'TOKENS','{}',null
)
,(
	'cm3b047f2000w3rpmdnv0bxpb',now(),now(),null,'qwen-max','(?i)^(qwen-max)(-[\da-zA-Z]+)*$'
	,null,0.00002,0.00006,null,'TOKENS','{}',null
)
;