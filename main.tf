# ==============================================================================
# TRISHULA CLOWD ARBITRAGE v4.1 — DUAL ACCOUNT MASTER IaC
# Platform: Multi-Cloud (AWS, Azure, GCP)
# Purpose: Provisioning all free-tier compute, database, and API layers
# Target: Account Set 2 (Research + Product)
# ==============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

# ------------------------------------------------------------------------------
# 1. AWS PROVIDER & RESOURCES (us-west-2 - Subscriber API Layer)
# ------------------------------------------------------------------------------
provider "aws" {
  region = "us-west-2"
}

# Always Free DynamoDB: trishula_subscribers (Limit: 25GB partition)
resource "aws_dynamodb_table" "subscribers" {
  name           = "trishula_subscribers"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "subscriber_id"

  attribute {
    name = "subscriber_id"
    type = "S"
  }

  tags = {
    Environment = "Production"
    System      = "Trishula-Arb-v4.1"
  }
}

# Always Free DynamoDB: trishula_api_keys
resource "aws_dynamodb_table" "api_keys" {
  name           = "trishula_api_keys"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "api_key"

  attribute {
    name = "api_key"
    type = "S"
  }

  tags = {
    Environment = "Production"
    System      = "Trishula-Arb-v4.1"
  }
}

# Always Free DynamoDB: trishula_usage_log
resource "aws_dynamodb_table" "usage_log" {
  name           = "trishula_usage_log"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "api_key"
  range_key      = "timestamp"

  attribute {
    name = "api_key"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  tags = {
    Environment = "Production"
    System      = "Trishula-Arb-v4.1"
  }
}

# Cross-Account IAM Role to read Account 1 DynamoDB
resource "aws_iam_role" "cross_account_reader" {
  name = "trishula-cross-account-reader"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy for cross-account read access to Account 1 picks_log DynamoDB table
resource "aws_iam_policy" "cross_account_db_read" {
  name        = "trishula-cross-account-db-read"
  description = "Allows reading the production picks log from Account 1"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:GetItem",
          "dynamodb:BatchGetItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:dynamodb:us-east-1:*:table/trishula_picks_log"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_cross_attach" {
  role       = aws_iam_role.cross_account_reader.name
  policy_arn = aws_iam_policy.cross_account_db_read.arn
}

# SQS Queue (Always Free 1M requests/mo)
resource "aws_sqs_queue" "discord_retry" {
  name                      = "trishula-discord-retry-queue"
  delay_seconds             = 90
  max_message_size          = 2048
  message_retention_seconds = 86400
  receive_wait_time_seconds = 10
}

# SNS Topic for alerts
resource "aws_sns_topic" "black_tier_alerts" {
  name = "trishula-black-tier-alerts"
}

# ------------------------------------------------------------------------------
# 2. AZURE PROVIDER & RESOURCES (westus - Subscriber Dashboard / OpenAI)
# ------------------------------------------------------------------------------
provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "arb_group" {
  name     = "trishula-arb-resources"
  location = "West US"
}

# Always Free Static Web App (100GB Free bandwidth)
resource "azurerm_static_site" "subscriber_portal" {
  name                = "trishula-subscriber-portal"
  resource_group_name = azurerm_resource_group.arb_group.name
  location            = "westus2"
  sku_tier            = "Free"
  sku_size            = "Free"
}

# Always Free Storage Account (Blob Storage 5GB)
resource "azurerm_storage_account" "static_storage" {
  name                     = "trishulafreestore"
  resource_group_name      = azurerm_resource_group.arb_group.name
  location                 = azurerm_resource_group.arb_group.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

# Cosmos DB (Always Free 1000 RU/s and 25GB Storage tier)
resource "azurerm_cosmosdb_account" "sub_cosmos" {
  name                = "trishula-sub-cosmos-db"
  location            = azurerm_resource_group.arb_group.location
  resource_group_name = azurerm_resource_group.arb_group.name
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  enable_free_tier = true

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.arb_group.location
    failover_priority = 0
  }
}

# ------------------------------------------------------------------------------
# 3. GCP PROVIDER & RESOURCES (us-central1 - Research Engine / ML training)
# ------------------------------------------------------------------------------
provider "google" {
  project = "trishula-research-4"
  region  = "us-central1"
}

# BigQuery Dataset (Always Free 10GB storage / 1TB Query limit)
resource "google_bigquery_dataset" "research_dataset" {
  dataset_id                  = "trishula_research"
  friendly_name               = "trishula_research"
  description                 = "BigQuery Picks Sink & ML Training Dataset for Self-Calibration"
  location                    = "US"
  default_table_expiration_ms = 3600000
}

# Always Free e2-micro VM Instance in us-central1
resource "google_compute_instance" "research_host" {
  name         = "trishula-research-host"
  machine_type = "e2-micro"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP - $0/mo always free
    }
  }

  metadata = {
    purpose = "Trishula-Research-ML-Calibration"
  }
}
