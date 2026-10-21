-- Baseline extracted from the provided production schema (PostgreSQL 15.8).
-- Fresh databases only. Not a migration; do not apply to the existing database.
-- Names are unqualified so tests can install the same objects in an isolated schema.
-- No owners, database creation, DROP statements or additional constraints.

CREATE TABLE podhods (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sportsmen character varying(200),
    original_message character varying(5000),
    volume real,
    date timestamp with time zone,
    tg_chat_id bigint,
    tg_message_id bigint
);

CREATE SEQUENCE bot_answers_id_seq AS integer;

CREATE TABLE bot_answers (
    id integer DEFAULT nextval('bot_answers_id_seq'::regclass) NOT NULL,
    podhod_id bigint NOT NULL,
    bot_message_id bigint NOT NULL,
    bot_chat_id bigint NOT NULL,
    CONSTRAINT id PRIMARY KEY (id)
);

ALTER SEQUENCE bot_answers_id_seq OWNED BY bot_answers.id;
