using System.Data.Entity.Migrations;
using System.Linq;
using ShopSphere.Domain.Entities;

namespace ShopSphere.Data.Migrations
{
    internal sealed class Configuration
        : DbMigrationsConfiguration<ShopSphere.Data.ApplicationDbContext>
    {
        public Configuration()
        {
            AutomaticMigrationsEnabled = false;
            MigrationsDirectory = @"Migrations";
        }

        protected override void Seed(ShopSphere.Data.ApplicationDbContext context)
        {
            // Create or update the sample categories.
            context.Categories.AddOrUpdate(
                c => c.Name,
                new Category { Name = "Women" },
                new Category { Name = "Men" },
                new Category { Name = "Accessories" }
            );

            context.SaveChanges();

            // Create or update the sample products.
            context.Products.AddOrUpdate(
                p => p.Name,
                new Product
                {
                    Name = "Classic Oversized Shirt",
                    Description = "Relaxed-fit everyday shirt in a soft cotton blend.",
                    Price = 1499m,
                    ImageUrl = "https://images.unsplash.com/photo-1598554747436-c9293d6a588f?w=700",
                    IsFeatured = true,
                    IsActive = true,
                    CategoryId = context.Categories.Single(c => c.Name == "Women").CategoryId
                },
                new Product
                {
                    Name = "Minimal Cotton T-Shirt",
                    Description = "A clean everyday essential with a comfortable fit.",
                    Price = 899m,
                    ImageUrl = "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=700",
                    IsFeatured = true,
                    IsActive = true,
                    CategoryId = context.Categories.Single(c => c.Name == "Men").CategoryId
                },
                new Product
                {
                    Name = "Everyday Canvas Tote",
                    Description = "A versatile carry-all for everyday use.",
                    Price = 699m,
                    ImageUrl = "https://images.unsplash.com/photo-1544816155-12df9643f363?w=700",
                    IsFeatured = true,
                    IsActive = true,
                    CategoryId = context.Categories.Single(c => c.Name == "Accessories").CategoryId
                }
            );

            context.SaveChanges();

            // Add variants only when the matching product/size/color is absent.
            AddVariantIfMissing(context, "Classic Oversized Shirt", "M", "Beige", 12);
            AddVariantIfMissing(context, "Classic Oversized Shirt", "L", "Beige", 8);
            AddVariantIfMissing(context, "Minimal Cotton T-Shirt", "M", "Black", 20);
            AddVariantIfMissing(context, "Everyday Canvas Tote", "One Size", "Natural", 15);

            context.SaveChanges();

            base.Seed(context);
        }

        private static void AddVariantIfMissing(
            ShopSphere.Data.ApplicationDbContext context,
            string productName,
            string size,
            string color,
            int stockQuantity)
        {
            var product = context.Products.Single(p => p.Name == productName);

            var variant = context.ProductVariants.SingleOrDefault(v =>
                v.ProductId == product.ProductId &&
                v.Size == size &&
                v.Color == color);

            if (variant == null)
            {
                context.ProductVariants.Add(new ProductVariant
                {
                    ProductId = product.ProductId,
                    Size = size,
                    Color = color,
                    StockQuantity = stockQuantity
                });
            }
        }
    }
}
