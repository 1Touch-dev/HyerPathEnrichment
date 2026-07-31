import {
  Building,
  MapPin,
  Phone,
  Globe,
  Star,
  Clock,
  MapPinned,
  DollarSign,
  Image as ImageIcon,
  MessageSquare,
  ExternalLink,
  Mail,
  Calendar,
  Info,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/src/lib/utils";
import type { BusinessProfile } from "@/src/lib/types";

interface BusinessProfileCardProps {
  business: BusinessProfile;
  className?: string;
}

export function BusinessProfileCard({ business, className }: BusinessProfileCardProps) {
  // Generate array of stars for rating
  const stars = Array.from({ length: 5 }, (_, i) => i < Math.floor(business.rating));

  // Check if we have data for each tab
  const hasDetails =
    business.openHours ||
    business.popularTimes ||
    business.timezone ||
    business.priceRange ||
    business.description ||
    business.about ||
    business.latitude ||
    business.reservations ||
    business.orderOnline ||
    business.menu;

  const hasReviews = business.reviewCount || business.reviewsPerRating || business.userReviews;

  const hasMedia = business.thumbnail || business.images || business.streetViewUrl;

  return (
    <Card className={cn("border-l-4 border-l-blue-500", className)}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 flex-wrap">
          <Building className="w-5 h-5 text-blue-600 dark:text-blue-400 shrink-0" />
          <span className="flex-1">{business.name}</span>
          {business.category && (
            <Badge variant="secondary" className="text-xs">
              {business.category}
            </Badge>
          )}
          {business.status && (
            <Badge variant={business.status === "open" ? "default" : "outline"} className="text-xs">
              {business.status}
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="details" disabled={!hasDetails}>
              Details
            </TabsTrigger>
            <TabsTrigger value="reviews" disabled={!hasReviews}>
              Reviews
            </TabsTrigger>
            <TabsTrigger value="media" disabled={!hasMedia}>
              Media
            </TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-3">
            {/* Rating */}
            <div className="flex items-center gap-2 pb-2 border-b">
              <div className="flex gap-0.5">
                {stars.map((filled, i) => (
                  <Star
                    key={i}
                    className={cn(
                      "w-4 h-4",
                      filled
                        ? "fill-yellow-400 text-yellow-400"
                        : "text-gray-300 dark:text-gray-700",
                    )}
                  />
                ))}
              </div>
              <span className="text-sm font-medium">{business.rating.toFixed(1)}</span>
              {business.reviewCount && (
                <span className="text-xs text-muted-foreground">({business.reviewCount})</span>
              )}
            </div>

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
                  className="text-sm text-primary hover:underline truncate flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  {business.website}
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            )}

            {/* Emails */}
            {business.emails && business.emails.length > 0 && (
              <div className="flex items-start gap-2">
                <Mail className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                <div className="flex flex-col gap-1">
                  {business.emails.map((email, i) => (
                    <a
                      key={i}
                      href={`mailto:${email}`}
                      className="text-sm text-primary hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {email}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Google Maps Link */}
            {business.latitude && business.longitude && (
              <div className="flex items-center gap-2 pt-2 border-t">
                <MapPinned className="w-4 h-4 text-muted-foreground shrink-0" />
                <a
                  href={`https://www.google.com/maps?q=${business.latitude},${business.longitude}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline flex items-center gap-1"
                  onClick={(e) => e.stopPropagation()}
                >
                  View on Google Maps
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            )}
          </TabsContent>

          {/* Details Tab */}
          <TabsContent value="details" className="space-y-3">
            {/* Operating Hours */}
            {business.openHours && (
              <div className="flex items-start gap-2">
                <Clock className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Hours</p>
                  <p className="text-sm whitespace-pre-line">{business.openHours}</p>
                </div>
              </div>
            )}

            {/* Popular Times */}
            {business.popularTimes && (
              <div className="flex items-start gap-2">
                <Calendar className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Popular Times</p>
                  <p className="text-sm">{business.popularTimes}</p>
                </div>
              </div>
            )}

            {/* Price Range */}
            {business.priceRange && (
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-muted-foreground shrink-0" />
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{business.priceRange}</span>
                  <Badge variant="outline" className="text-xs">
                    Price
                  </Badge>
                </div>
              </div>
            )}

            {/* Timezone */}
            {business.timezone && (
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-muted-foreground shrink-0" />
                <span className="text-sm text-muted-foreground">{business.timezone}</span>
              </div>
            )}

            {/* Description */}
            {business.description && (
              <div className="flex items-start gap-2 pt-2 border-t">
                <Info className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Description</p>
                  <p className="text-sm">{business.description}</p>
                </div>
              </div>
            )}

            {/* About */}
            {business.about && (
              <div className="flex items-start gap-2">
                <Info className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground mb-1">About</p>
                  <p className="text-sm">{business.about}</p>
                </div>
              </div>
            )}

            {/* Commerce Links */}
            {(business.reservations || business.orderOnline || business.menu) && (
              <div className="flex flex-wrap gap-2 pt-2 border-t">
                {business.reservations && (
                  <a
                    href={business.reservations}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Make Reservation
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {business.orderOnline && (
                  <a
                    href={business.orderOnline}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Order Online
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
                {business.menu && (
                  <a
                    href={business.menu}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs px-3 py-1.5 rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/90 flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View Menu
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            )}

            {/* Location Coordinates */}
            {business.latitude && business.longitude && (
              <div className="flex items-start gap-2 pt-2 border-t">
                <MapPinned className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Coordinates</p>
                  <p className="text-sm font-mono">
                    {business.latitude.toFixed(6)}, {business.longitude.toFixed(6)}
                  </p>
                  {business.placeId && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Place ID: {business.placeId}
                    </p>
                  )}
                </div>
              </div>
            )}
          </TabsContent>

          {/* Reviews Tab */}
          <TabsContent value="reviews" className="space-y-3">
            {/* Review Count and Link */}
            {business.reviewCount && (
              <div className="flex items-center justify-between pb-2 border-b">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm font-medium">
                    {business.reviewCount} {business.reviewCount === 1 ? "Review" : "Reviews"}
                  </span>
                </div>
                {business.reviewsLink && (
                  <a
                    href={business.reviewsLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:underline flex items-center gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    View All
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </div>
            )}

            {/* Rating Breakdown */}
            {business.reviewsPerRating && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Rating Distribution</p>
                {Object.entries(business.reviewsPerRating)
                  .sort(([a], [b]) => Number(b) - Number(a))
                  .map(([rating, count]) => {
                    const total = business.reviewCount || 1;
                    const percentage = (count / total) * 100;
                    return (
                      <div key={rating} className="flex items-center gap-2">
                        <div className="flex items-center gap-1 w-12">
                          <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
                          <span className="text-xs">{rating}</span>
                        </div>
                        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-yellow-400"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-12 text-right">
                          {count}
                        </span>
                      </div>
                    );
                  })}
              </div>
            )}

            {/* Individual Reviews */}
            {business.userReviews && business.userReviews.length > 0 && (
              <div className="space-y-3 pt-2 border-t">
                <p className="text-xs font-medium text-muted-foreground">Recent Reviews</p>
                {business.userReviews.slice(0, 3).map((review, i) => (
                  <div key={i} className="p-3 rounded-lg bg-muted/50 space-y-1">
                    {review.rating !== undefined && (
                      <div className="flex gap-0.5">
                        {Array.from({ length: 5 }, (_, j) => (
                          <Star
                            key={j}
                            className={cn(
                              "w-3 h-3",
                              j < review.rating!
                                ? "fill-yellow-400 text-yellow-400"
                                : "text-gray-300 dark:text-gray-700",
                            )}
                          />
                        ))}
                      </div>
                    )}
                    {review.text && <p className="text-sm">{review.text}</p>}
                    {review.timestamp && (
                      <p className="text-xs text-muted-foreground">{review.timestamp}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </TabsContent>

          {/* Media Tab */}
          <TabsContent value="media" className="space-y-3">
            {/* Thumbnail */}
            {business.thumbnail && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground">Thumbnail</p>
                <img
                  src={business.thumbnail}
                  alt={business.name}
                  className="w-full h-48 object-cover rounded-lg"
                />
              </div>
            )}

            {/* Image Gallery */}
            {business.images && business.images.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <ImageIcon className="w-3 h-3" />
                  Photos ({business.images.length})
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {business.images.slice(0, 4).map((image, i) => (
                    <a
                      key={i}
                      href={image}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="relative aspect-video rounded-lg overflow-hidden group"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <img
                        src={image}
                        alt={`${business.name} photo ${i + 1}`}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                      />
                      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                        <ExternalLink className="w-4 h-4 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    </a>
                  ))}
                </div>
                {business.images.length > 4 && (
                  <p className="text-xs text-muted-foreground text-center">
                    +{business.images.length - 4} more photos
                  </p>
                )}
              </div>
            )}

            {/* Street View */}
            {business.streetViewUrl && (
              <div className="pt-2 border-t">
                <a
                  href={business.streetViewUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-3 rounded-lg bg-muted hover:bg-muted/80 transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <MapPinned className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm">View Street View</span>
                  <ExternalLink className="w-3 h-3 ml-auto" />
                </a>
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
