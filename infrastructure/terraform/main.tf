# LeadSynt — Azure infrastructure skeleton
# NOT applied by this repo. Requires a real subscription and reviewed values.
#
#   terraform init && terraform plan
#
# Values must come from the secrets store / env — never commit real ones.

terraform {
  required_version = ">= 1.6"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.90" }
  }
}

provider "azurerm" {
  features {}
}

variable "resource_group" { default = "leadsynt-prod" }
variable "sql_admin_user" {
  default     = "leadsynt"
  sensitive   = true
}
variable "sql_admin_password" {
  type        = string
  sensitive   = true
}
variable "sql_sku" { default = "GeneralPurpose_DdSKVMemory16_v2" } # 8 vCore, 32 GB — resize to need

resource "azurerm_resource_group" "main" {
  name     = var.resource_group
  location = "eastus2" # choose region for data residency
}

resource "azurerm_mssql_server" "main" {
  name                         = "leadsynt-sql"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  administrator_login          = var.sql_admin_user
  administrator_login_password = var.sql_admin_password
  version                      = "12.0" # SQL Server 2022
  minimum_tls_version          = "1.2"
}

resource "azurerm_mssql_database" "main" {
  name                        = "LeadSynt"
  server_name                 = azurerm_mssql_server.main.name
  resource_group_name         = azurerm_resource_group.main.name
  location                    = azurerm_resource_group.main.location
  sku_name                    = var.sql_sku
  zone_redundant              = true
}

# NOTE: AAD admin requires a real object id from your directory —
# uncomment and fill in before applying:
#
# resource "azurerm_mssql_server_aad_admin" "main" {
#   server_name             = azurerm_mssql_server.main.name
#   administrator_login     = "leadsynt-admin"
#   # object_id               = "<your-directory-object-id>"
# }

# NOTE: In a real deployment the app reaches SQL through a network-secured
# path (private endpoint / VM subnet) with a least-privilege login that is
# DB-owner on LeadSynt only — model that as a second server + firewall rule
# once the network topology is decided.

# Storage for nightly .bak files
resource "azurerm_storage_account" "backups" {
  name                = "leadsyntbackups"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  account_tier        = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_storage_container" "backups" {
  name                  = "mssql"
  storage_account_name  = azurerm_storage_account.backups.name
  container_access_type = "Private"
}
