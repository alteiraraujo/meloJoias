-- Melo Joias: SQL de referencia da migracao inicial SQLite.
-- Para instalar, use manage.py migrate.
-- Atualizacao: 0002_product_ean13 adiciona e preenche core_product.ean13
-- (varchar(13), NOT NULL, UNIQUE). O preenchimento usa uma migracao Python;
-- este arquivo historico nao substitui a execucao das migracoes Django.
-- 0003_product_photo adiciona core_product.photo (caminho da foto local).
-- 0004_consignment_tracking adiciona core_consignment.tracking_code.
-- 0008_consignment_signed_document adiciona signed_document (caminho do PDF)
-- e signed_document_uploaded_at (data/hora do upload) a core_consignment.
-- 0009_consignment_shipping_details adiciona shipping_responsible (varchar(160))
-- e shipping_method (varchar(80)), opcionais, a core_consignment.
-- 0010_postal_addresses_and_sender cria core_senderprofile e adiciona os campos
-- postais a core_client: postal_code, street, number, complement, neighborhood,
-- city e state. O campo address anterior e seus valores sao preservados.

BEGIN;
--
-- Create model Category
--
CREATE TABLE "core_category" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(100) NOT NULL UNIQUE, "description" text NOT NULL, "active" bool NOT NULL);
--
-- Create model Client
--
CREATE TABLE "core_client" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(160) NOT NULL, "document" varchar(25) NOT NULL, "phone" varchar(30) NOT NULL, "email" varchar(254) NOT NULL, "address" text NOT NULL, "notes" text NOT NULL, "active" bool NOT NULL, "created_at" datetime NOT NULL);
--
-- Create model CostType
--
CREATE TABLE "core_costtype" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(100) NOT NULL UNIQUE, "description" text NOT NULL, "active" bool NOT NULL);
--
-- Create model Consignment
--
CREATE TABLE "core_consignment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sent_date" date NOT NULL, "due_date" date NOT NULL, "notes" text NOT NULL, "status" varchar(12) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "client_id" bigint NOT NULL REFERENCES "core_client" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model Contact
--
CREATE TABLE "core_contact" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "name" varchar(160) NOT NULL, "relationship" varchar(100) NOT NULL, "phone" varchar(30) NOT NULL, "email" varchar(254) NOT NULL, "notes" text NOT NULL, "client_id" bigint NOT NULL REFERENCES "core_client" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model ConsignmentContact
--
CREATE TABLE "core_consignmentcontact" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "contact_id" bigint NOT NULL REFERENCES "core_contact" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Add field contacts to consignment
--
CREATE TABLE "new__core_consignment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sent_date" date NOT NULL, "due_date" date NOT NULL, "notes" text NOT NULL, "status" varchar(12) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "client_id" bigint NOT NULL REFERENCES "core_client" ("id") DEFERRABLE INITIALLY DEFERRED);
INSERT INTO "new__core_consignment" ("id", "sent_date", "due_date", "notes", "status", "created_at", "updated_at", "client_id") SELECT "id", "sent_date", "due_date", "notes", "status", "created_at", "updated_at", "client_id" FROM "core_consignment";
DROP TABLE "core_consignment";
ALTER TABLE "new__core_consignment" RENAME TO "core_consignment";
CREATE INDEX "core_contact_client_id_20312e64" ON "core_contact" ("client_id");
CREATE INDEX "core_consignmentcontact_consignment_id_047f95a3" ON "core_consignmentcontact" ("consignment_id");
CREATE INDEX "core_consignmentcontact_contact_id_832077da" ON "core_consignmentcontact" ("contact_id");
CREATE INDEX "core_consignment_client_id_374fa1d6" ON "core_consignment" ("client_id");
--
-- Create model Payment
--
CREATE TABLE "core_payment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "amount" decimal NOT NULL, "paid_date" date NOT NULL, "method" varchar(12) NOT NULL, "notes" text NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model Product
--
CREATE TABLE "core_product" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sku" varchar(40) NOT NULL UNIQUE, "name" varchar(160) NOT NULL, "description" text NOT NULL, "sale_price" decimal NOT NULL, "stock_quantity" integer unsigned NOT NULL CHECK ("stock_quantity" >= 0), "minimum_stock" integer unsigned NOT NULL CHECK ("minimum_stock" >= 0), "active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "category_id" bigint NOT NULL REFERENCES "core_category" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model ConsignmentItem
--
CREATE TABLE "core_consignmentitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "unit_price" decimal NOT NULL, "sold_quantity" integer unsigned NOT NULL CHECK ("sold_quantity" >= 0), "returned_quantity" integer unsigned NOT NULL CHECK ("returned_quantity" >= 0), "product_name" varchar(160) NOT NULL, "product_sku" varchar(40) NOT NULL, "unit_cost" decimal NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model ProductCost
--
CREATE TABLE "core_productcost" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "description" varchar(200) NOT NULL, "amount" decimal NOT NULL, "cost_type_id" bigint NOT NULL REFERENCES "core_costtype" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model StockMovement
--
CREATE TABLE "core_stockmovement" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kind" varchar(12) NOT NULL, "quantity" integer NOT NULL, "note" varchar(250) NOT NULL, "created_at" datetime NOT NULL, "consignment_id" bigint NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create constraint unique_consignment_contact on model consignmentcontact
--
CREATE TABLE "new__core_consignmentcontact" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "contact_id" bigint NOT NULL REFERENCES "core_contact" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_consignment_contact" UNIQUE ("consignment_id", "contact_id"));
INSERT INTO "new__core_consignmentcontact" ("id", "consignment_id", "contact_id") SELECT "id", "consignment_id", "contact_id" FROM "core_consignmentcontact";
DROP TABLE "core_consignmentcontact";
ALTER TABLE "new__core_consignmentcontact" RENAME TO "core_consignmentcontact";
CREATE INDEX "core_payment_consignment_id_f5369549" ON "core_payment" ("consignment_id");
CREATE INDEX "core_product_category_id_b9d8ff9f" ON "core_product" ("category_id");
CREATE INDEX "core_consignmentitem_consignment_id_60cd51ef" ON "core_consignmentitem" ("consignment_id");
CREATE INDEX "core_consignmentitem_product_id_a331b437" ON "core_consignmentitem" ("product_id");
CREATE INDEX "core_productcost_cost_type_id_5719b81e" ON "core_productcost" ("cost_type_id");
CREATE INDEX "core_productcost_product_id_a63bfbcc" ON "core_productcost" ("product_id");
CREATE INDEX "core_stockmovement_consignment_id_4558cf74" ON "core_stockmovement" ("consignment_id");
CREATE INDEX "core_stockmovement_product_id_bd647177" ON "core_stockmovement" ("product_id");
CREATE INDEX "core_consignmentcontact_consignment_id_047f95a3" ON "core_consignmentcontact" ("consignment_id");
CREATE INDEX "core_consignmentcontact_contact_id_832077da" ON "core_consignmentcontact" ("contact_id");
--
-- Create index consignment_status_due on field(s) status, due_date of model consignment
--
CREATE INDEX "consignment_status_due" ON "core_consignment" ("status", "due_date");
--
-- Create constraint consignment_dates_ordered on model consignment
--
CREATE TABLE "new__core_consignment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sent_date" date NOT NULL, "due_date" date NOT NULL, "notes" text NOT NULL, "status" varchar(12) NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "client_id" bigint NOT NULL REFERENCES "core_client" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "consignment_dates_ordered" CHECK ("due_date" >= ("sent_date")));
INSERT INTO "new__core_consignment" ("id", "sent_date", "due_date", "notes", "status", "created_at", "updated_at", "client_id") SELECT "id", "sent_date", "due_date", "notes", "status", "created_at", "updated_at", "client_id" FROM "core_consignment";
DROP TABLE "core_consignment";
ALTER TABLE "new__core_consignment" RENAME TO "core_consignment";
CREATE INDEX "core_consignment_client_id_374fa1d6" ON "core_consignment" ("client_id");
CREATE INDEX "consignment_status_due" ON "core_consignment" ("status", "due_date");
--
-- Create constraint payment_positive on model payment
--
CREATE TABLE "new__core_payment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "amount" decimal NOT NULL, "paid_date" date NOT NULL, "method" varchar(12) NOT NULL, "notes" text NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "payment_positive" CHECK ("amount" > '0'));
INSERT INTO "new__core_payment" ("id", "amount", "paid_date", "method", "notes", "consignment_id") SELECT "id", "amount", "paid_date", "method", "notes", "consignment_id" FROM "core_payment";
DROP TABLE "core_payment";
ALTER TABLE "new__core_payment" RENAME TO "core_payment";
CREATE INDEX "core_payment_consignment_id_f5369549" ON "core_payment" ("consignment_id");
--
-- Create constraint product_price_nonnegative on model product
--
CREATE TABLE "new__core_product" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sku" varchar(40) NOT NULL UNIQUE, "name" varchar(160) NOT NULL, "description" text NOT NULL, "sale_price" decimal NOT NULL, "stock_quantity" integer unsigned NOT NULL CHECK ("stock_quantity" >= 0), "minimum_stock" integer unsigned NOT NULL CHECK ("minimum_stock" >= 0), "active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "category_id" bigint NOT NULL REFERENCES "core_category" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "product_price_nonnegative" CHECK ("sale_price" >= '0'));
INSERT INTO "new__core_product" ("id", "sku", "name", "description", "sale_price", "stock_quantity", "minimum_stock", "active", "created_at", "updated_at", "category_id") SELECT "id", "sku", "name", "description", "sale_price", "stock_quantity", "minimum_stock", "active", "created_at", "updated_at", "category_id" FROM "core_product";
DROP TABLE "core_product";
ALTER TABLE "new__core_product" RENAME TO "core_product";
CREATE INDEX "core_product_category_id_b9d8ff9f" ON "core_product" ("category_id");
--
-- Create constraint product_stock_nonnegative on model product
--
CREATE TABLE "new__core_product" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sku" varchar(40) NOT NULL UNIQUE, "name" varchar(160) NOT NULL, "description" text NOT NULL, "sale_price" decimal NOT NULL, "stock_quantity" integer unsigned NOT NULL CHECK ("stock_quantity" >= 0), "minimum_stock" integer unsigned NOT NULL CHECK ("minimum_stock" >= 0), "active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "category_id" bigint NOT NULL REFERENCES "core_category" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "product_price_nonnegative" CHECK ("sale_price" >= '0'), CONSTRAINT "product_stock_nonnegative" CHECK ("stock_quantity" >= 0));
INSERT INTO "new__core_product" ("id", "sku", "name", "description", "sale_price", "stock_quantity", "minimum_stock", "active", "created_at", "updated_at", "category_id") SELECT "id", "sku", "name", "description", "sale_price", "stock_quantity", "minimum_stock", "active", "created_at", "updated_at", "category_id" FROM "core_product";
DROP TABLE "core_product";
ALTER TABLE "new__core_product" RENAME TO "core_product";
CREATE INDEX "core_product_category_id_b9d8ff9f" ON "core_product" ("category_id");
--
-- Create constraint product_minimum_nonnegative on model product
--
CREATE TABLE "new__core_product" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "sku" varchar(40) NOT NULL UNIQUE, "name" varchar(160) NOT NULL, "description" text NOT NULL, "sale_price" decimal NOT NULL, "stock_quantity" integer unsigned NOT NULL CHECK ("stock_quantity" >= 0), "minimum_stock" integer unsigned NOT NULL CHECK ("minimum_stock" >= 0), "active" bool NOT NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "category_id" bigint NOT NULL REFERENCES "core_category" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "product_price_nonnegative" CHECK ("sale_price" >= '0'), CONSTRAINT "product_stock_nonnegative" CHECK ("stock_quantity" >= 0), CONSTRAINT "product_minimum_nonnegative" CHECK ("minimum_stock" >= 0));
INSERT INTO "new__core_product" ("id", "sku", "name", "description", "sale_price", "stock_quantity", "minimum_stock", "active", "created_at", "updated_at", "category_id") SELECT "id", "sku", "name", "description", "sale_price", "stock_quantity", "minimum_stock", "active", "created_at", "updated_at", "category_id" FROM "core_product";
DROP TABLE "core_product";
ALTER TABLE "new__core_product" RENAME TO "core_product";
CREATE INDEX "core_product_category_id_b9d8ff9f" ON "core_product" ("category_id");
--
-- Create constraint unique_consignment_product on model consignmentitem
--
CREATE TABLE "new__core_consignmentitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "unit_price" decimal NOT NULL, "sold_quantity" integer unsigned NOT NULL CHECK ("sold_quantity" >= 0), "returned_quantity" integer unsigned NOT NULL CHECK ("returned_quantity" >= 0), "product_name" varchar(160) NOT NULL, "product_sku" varchar(40) NOT NULL, "unit_cost" decimal NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_consignment_product" UNIQUE ("consignment_id", "product_id"));
INSERT INTO "new__core_consignmentitem" ("id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id") SELECT "id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id" FROM "core_consignmentitem";
DROP TABLE "core_consignmentitem";
ALTER TABLE "new__core_consignmentitem" RENAME TO "core_consignmentitem";
CREATE INDEX "core_consignmentitem_consignment_id_60cd51ef" ON "core_consignmentitem" ("consignment_id");
CREATE INDEX "core_consignmentitem_product_id_a331b437" ON "core_consignmentitem" ("product_id");
--
-- Create constraint item_quantity_positive on model consignmentitem
--
CREATE TABLE "new__core_consignmentitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "unit_price" decimal NOT NULL, "sold_quantity" integer unsigned NOT NULL CHECK ("sold_quantity" >= 0), "returned_quantity" integer unsigned NOT NULL CHECK ("returned_quantity" >= 0), "product_name" varchar(160) NOT NULL, "product_sku" varchar(40) NOT NULL, "unit_cost" decimal NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_consignment_product" UNIQUE ("consignment_id", "product_id"), CONSTRAINT "item_quantity_positive" CHECK ("quantity" > 0));
INSERT INTO "new__core_consignmentitem" ("id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id") SELECT "id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id" FROM "core_consignmentitem";
DROP TABLE "core_consignmentitem";
ALTER TABLE "new__core_consignmentitem" RENAME TO "core_consignmentitem";
CREATE INDEX "core_consignmentitem_consignment_id_60cd51ef" ON "core_consignmentitem" ("consignment_id");
CREATE INDEX "core_consignmentitem_product_id_a331b437" ON "core_consignmentitem" ("product_id");
--
-- Create constraint item_prices_nonnegative on model consignmentitem
--
CREATE TABLE "new__core_consignmentitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "unit_price" decimal NOT NULL, "sold_quantity" integer unsigned NOT NULL CHECK ("sold_quantity" >= 0), "returned_quantity" integer unsigned NOT NULL CHECK ("returned_quantity" >= 0), "product_name" varchar(160) NOT NULL, "product_sku" varchar(40) NOT NULL, "unit_cost" decimal NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_consignment_product" UNIQUE ("consignment_id", "product_id"), CONSTRAINT "item_quantity_positive" CHECK ("quantity" > 0), CONSTRAINT "item_prices_nonnegative" CHECK (("unit_price" >= '0' AND "unit_cost" >= '0')));
INSERT INTO "new__core_consignmentitem" ("id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id") SELECT "id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id" FROM "core_consignmentitem";
DROP TABLE "core_consignmentitem";
ALTER TABLE "new__core_consignmentitem" RENAME TO "core_consignmentitem";
CREATE INDEX "core_consignmentitem_consignment_id_60cd51ef" ON "core_consignmentitem" ("consignment_id");
CREATE INDEX "core_consignmentitem_product_id_a331b437" ON "core_consignmentitem" ("product_id");
--
-- Create constraint item_settlement_nonnegative on model consignmentitem
--
CREATE TABLE "new__core_consignmentitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "unit_price" decimal NOT NULL, "sold_quantity" integer unsigned NOT NULL CHECK ("sold_quantity" >= 0), "returned_quantity" integer unsigned NOT NULL CHECK ("returned_quantity" >= 0), "product_name" varchar(160) NOT NULL, "product_sku" varchar(40) NOT NULL, "unit_cost" decimal NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_consignment_product" UNIQUE ("consignment_id", "product_id"), CONSTRAINT "item_quantity_positive" CHECK ("quantity" > 0), CONSTRAINT "item_prices_nonnegative" CHECK (("unit_price" >= '0' AND "unit_cost" >= '0')), CONSTRAINT "item_settlement_nonnegative" CHECK (("sold_quantity" >= 0 AND "returned_quantity" >= 0)));
INSERT INTO "new__core_consignmentitem" ("id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id") SELECT "id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id" FROM "core_consignmentitem";
DROP TABLE "core_consignmentitem";
ALTER TABLE "new__core_consignmentitem" RENAME TO "core_consignmentitem";
CREATE INDEX "core_consignmentitem_consignment_id_60cd51ef" ON "core_consignmentitem" ("consignment_id");
CREATE INDEX "core_consignmentitem_product_id_a331b437" ON "core_consignmentitem" ("product_id");
--
-- Create constraint item_settlement_within_quantity on model consignmentitem
--
CREATE TABLE "new__core_consignmentitem" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "quantity" integer unsigned NOT NULL CHECK ("quantity" >= 0), "unit_price" decimal NOT NULL, "sold_quantity" integer unsigned NOT NULL CHECK ("sold_quantity" >= 0), "returned_quantity" integer unsigned NOT NULL CHECK ("returned_quantity" >= 0), "product_name" varchar(160) NOT NULL, "product_sku" varchar(40) NOT NULL, "unit_cost" decimal NOT NULL, "consignment_id" bigint NOT NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "unique_consignment_product" UNIQUE ("consignment_id", "product_id"), CONSTRAINT "item_quantity_positive" CHECK ("quantity" > 0), CONSTRAINT "item_prices_nonnegative" CHECK (("unit_price" >= '0' AND "unit_cost" >= '0')), CONSTRAINT "item_settlement_nonnegative" CHECK (("sold_quantity" >= 0 AND "returned_quantity" >= 0)), CONSTRAINT "item_settlement_within_quantity" CHECK ("quantity" >= ("sold_quantity" + "returned_quantity")));
INSERT INTO "new__core_consignmentitem" ("id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id") SELECT "id", "quantity", "unit_price", "sold_quantity", "returned_quantity", "product_name", "product_sku", "unit_cost", "consignment_id", "product_id" FROM "core_consignmentitem";
DROP TABLE "core_consignmentitem";
ALTER TABLE "new__core_consignmentitem" RENAME TO "core_consignmentitem";
CREATE INDEX "core_consignmentitem_consignment_id_60cd51ef" ON "core_consignmentitem" ("consignment_id");
CREATE INDEX "core_consignmentitem_product_id_a331b437" ON "core_consignmentitem" ("product_id");
--
-- Create constraint product_cost_nonnegative on model productcost
--
CREATE TABLE "new__core_productcost" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "description" varchar(200) NOT NULL, "amount" decimal NOT NULL, "cost_type_id" bigint NOT NULL REFERENCES "core_costtype" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "product_cost_nonnegative" CHECK ("amount" >= '0'));
INSERT INTO "new__core_productcost" ("id", "description", "amount", "cost_type_id", "product_id") SELECT "id", "description", "amount", "cost_type_id", "product_id" FROM "core_productcost";
DROP TABLE "core_productcost";
ALTER TABLE "new__core_productcost" RENAME TO "core_productcost";
CREATE INDEX "core_productcost_cost_type_id_5719b81e" ON "core_productcost" ("cost_type_id");
CREATE INDEX "core_productcost_product_id_a63bfbcc" ON "core_productcost" ("product_id");
--
-- Create constraint stock_movement_nonzero on model stockmovement
--
CREATE TABLE "new__core_stockmovement" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kind" varchar(12) NOT NULL, "quantity" integer NOT NULL, "note" varchar(250) NOT NULL, "created_at" datetime NOT NULL, "consignment_id" bigint NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "stock_movement_nonzero" CHECK (NOT ("quantity" = 0)));
INSERT INTO "new__core_stockmovement" ("id", "kind", "quantity", "note", "created_at", "consignment_id", "product_id") SELECT "id", "kind", "quantity", "note", "created_at", "consignment_id", "product_id" FROM "core_stockmovement";
DROP TABLE "core_stockmovement";
ALTER TABLE "new__core_stockmovement" RENAME TO "core_stockmovement";
CREATE INDEX "core_stockmovement_consignment_id_4558cf74" ON "core_stockmovement" ("consignment_id");
CREATE INDEX "core_stockmovement_product_id_bd647177" ON "core_stockmovement" ("product_id");
--
-- Create constraint stock_movement_sign on model stockmovement
--
CREATE TABLE "new__core_stockmovement" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "kind" varchar(12) NOT NULL, "quantity" integer NOT NULL, "note" varchar(250) NOT NULL, "created_at" datetime NOT NULL, "consignment_id" bigint NULL REFERENCES "core_consignment" ("id") DEFERRABLE INITIALLY DEFERRED, "product_id" bigint NOT NULL REFERENCES "core_product" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "stock_movement_nonzero" CHECK (NOT ("quantity" = 0)), CONSTRAINT "stock_movement_sign" CHECK ((("kind" IN ('in', 'return') AND "quantity" > 0) OR ("kind" = 'out' AND "quantity" < 0) OR "kind" = 'adjustment')));
INSERT INTO "new__core_stockmovement" ("id", "kind", "quantity", "note", "created_at", "consignment_id", "product_id") SELECT "id", "kind", "quantity", "note", "created_at", "consignment_id", "product_id" FROM "core_stockmovement";
DROP TABLE "core_stockmovement";
ALTER TABLE "new__core_stockmovement" RENAME TO "core_stockmovement";
CREATE INDEX "core_stockmovement_consignment_id_4558cf74" ON "core_stockmovement" ("consignment_id");
CREATE INDEX "core_stockmovement_product_id_bd647177" ON "core_stockmovement" ("product_id");
COMMIT;
