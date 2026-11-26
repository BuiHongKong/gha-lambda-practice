resource "aws_db_subnet_group" "lab" {
  name        = local.name
  description = "Two AZs required by RDS. The instance runs in the first only."
  subnet_ids  = aws_subnet.private[*].id
}

resource "aws_db_instance" "lab" {
  identifier     = local.name
  engine         = "mysql"
  engine_version = var.mysql_engine_version
  instance_class = "db.t4g.micro"

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.lab.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  availability_zone      = aws_subnet.private[0].availability_zone
  multi_az               = false
  publicly_accessible    = false

  backup_retention_period    = 1
  skip_final_snapshot        = true
  deletion_protection        = false
  auto_minor_version_upgrade = true
  apply_immediately          = true
  copy_tags_to_snapshot      = true
}
