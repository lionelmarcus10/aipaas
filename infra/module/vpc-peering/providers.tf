provider "aws" {
  alias  = "this"
  region = var.aws_region
}

provider "aws" {
  alias  = "peer"
  region = var.aws_region
}
