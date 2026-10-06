import { useEffect, useState } from "react";

import { getProduct, listProducts } from "../api/products";
import type { ProductDetail, ProductSummary } from "../types/api";
import { formatApiError } from "../utils/format";

export function useProductCatalog(productId: string) {
  const [products, setProducts] = useState<ProductSummary[]>([]);
  const [productDetail, setProductDetail] = useState<ProductDetail | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    void listProducts()
      .then(setProducts)
      .catch((error) => setCatalogError(formatApiError(error)));
  }, []);

  useEffect(() => {
    if (!productId) {
      setProductDetail(null);
      return;
    }
    let active = true;
    void getProduct(productId)
      .then((product) => {
        if (active) setProductDetail(product);
      })
      .catch((error) => {
        if (active) setCatalogError(formatApiError(error));
      });
    return () => {
      active = false;
    };
  }, [productId]);

  return { products, productDetail, catalogError };
}
