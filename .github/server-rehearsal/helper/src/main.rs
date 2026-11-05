//! 一次性 SQLx 迁移演练入口
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let url = std::env::var("DATABASE_URL")?;
    let dir = std::env::args().nth(1).expect("migration directory");
    let pool = sqlx::PgPool::connect(&url).await?;
    let migrator = sqlx::migrate::Migrator::new(std::path::Path::new(&dir)).await?;
    migrator.run(&pool).await?;
    pool.close().await;
    Ok(())
}
