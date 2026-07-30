import { Building, MapPin, Phone, Globe, Star } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/src/lib/utils";
import type { BusinessProfile } from "@/src/lib/types";

interface BusinessProfileCardProps {
  business: BusinessProfile;
  className?: string;
}

export function BusinessProfileCard({ business, className }: BusinessProfileCardProps) {
  // Generate array of stars for rating
  const stars = Array.from({ length: 5 }, (_, i) => i < Math.floor(business.rating));

  return (
    <Card className={cn("border-l-4 border-l-blue-500", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          {business.name}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Address */}
        <div className="flex items-start gap-2">
          <MapPin className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
          <span className="text-sm">{business.address}</span>
        </div>

        {/* Phone */}
        {business.phone && (
          <div className="flex items-center gap-2">
            <Phone className="w-4 h-4 text-muted-foreground shrink-0" />
            <a
              href={`tel:${business.phone}`}
              className="text-sm text-primary hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {business.phone}
            </a>
          </div>
        )}

        {/* Website */}
        {business.website && (
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-muted-foreground shrink-0" />
            <a
              href={business.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline truncate"
              onClick={(e) => e.stopPropagation()}
            >
              {business.website}
            </a>
          </div>
        )}

        {/* Rating */}
        <div className="flex items-center gap-2 pt-2 border-t">
          <div className="flex gap-0.5">
            {stars.map((filled, i) => (
              <Star
                key={i}
                className={cn(
                  "w-4 h-4",
                  filled ? "fill-yellow-400 text-yellow-400" : "text-gray-300 dark:text-gray-700",
                )}
              />
            ))}
          </div>
          <span className="text-sm font-medium">{business.rating.toFixed(1)}</span>
        </div>
      </CardContent>
    </Card>
  );
}
