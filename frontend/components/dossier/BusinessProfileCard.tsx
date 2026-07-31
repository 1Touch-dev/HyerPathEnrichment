import { useState } from "react";
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
  X,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/src/lib/utils";
import type { BusinessProfile } from "@/src/lib/types";

interface BusinessProfileCardProps {
  business: BusinessProfile;
  className?: string;
}

export function BusinessProfileCard({ business, className }: BusinessProfileCardProps) {
  const [showAllPhotos, setShowAllPhotos] = useState(false);
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
          <TabsContent value="details" className="space-y-4">
            {/* Operating Hours - Featured */}
            {business.openHours && (
              <div className="rounded-lg bg-muted/50 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Clock className="w-5 h-5 text-primary" />
                  <h4 className="font-semibold text-sm">Business Hours</h4>
                </div>
                <div className="text-sm leading-relaxed whitespace-pre-line">
                  {business.openHours}
                </div>
              </div>
            )}

            {/* Quick Info Grid */}
            <div className="grid gap-3">
              {/* Price Range */}
              {business.priceRange && (
                <div className="flex items-center justify-between p-3 rounded-lg border bg-card">
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Price Range</span>
                  </div>
                  <Badge variant="secondary">{business.priceRange}</Badge>
                </div>
              )}

              {/* Timezone */}
              {business.timezone && (
                <div className="flex items-center justify-between p-3 rounded-lg border bg-card">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Timezone</span>
                  </div>
                  <span className="text-sm text-muted-foreground">{business.timezone}</span>
                </div>
              )}

              {/* Location Coordinates */}
              {business.latitude && business.longitude && (
                <div className="p-3 rounded-lg border bg-card">
                  <div className="flex items-center gap-2 mb-2">
                    <MapPinned className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm font-medium">Location</span>
                  </div>
                  <p className="text-sm font-mono text-muted-foreground">
                    {business.latitude.toFixed(6)}, {business.longitude.toFixed(6)}
                  </p>
                  {business.placeId && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Place ID: {business.placeId}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Description */}
            {business.description && (
              <div className="rounded-lg border bg-card p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Info className="w-4 h-4 text-muted-foreground" />
                  <h4 className="font-semibold text-sm">Description</h4>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {business.description}
                </p>
              </div>
            )}

            {/* About - Parse JSON and display nicely */}
            {business.about &&
              (() => {
                try {
                  const aboutData =
                    typeof business.about === "string"
                      ? JSON.parse(business.about)
                      : business.about;

                  if (Array.isArray(aboutData) && aboutData.length > 0) {
                    return (
                      <div className="rounded-lg border bg-card p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Info className="w-4 h-4 text-muted-foreground" />
                          <h4 className="font-semibold text-sm">Amenities & Features</h4>
                        </div>
                        <div className="space-y-3">
                          {aboutData.map((section: any, idx: number) => (
                            <div key={idx}>
                              <p className="text-xs font-semibold text-primary mb-1.5">
                                {section.name || section.id}
                              </p>
                              <div className="grid grid-cols-2 gap-1.5">
                                {section.options?.map((option: any, optIdx: number) => (
                                  <div key={optIdx} className="flex items-start gap-1.5 text-xs">
                                    <span
                                      className={
                                        option.enabled ? "text-green-600" : "text-muted-foreground"
                                      }
                                    >
                                      {option.enabled ? "✓" : "○"}
                                    </span>
                                    <span className={option.enabled ? "" : "text-muted-foreground"}>
                                      {option.name}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  }
                } catch (e) {
                  // Fallback to plain text if JSON parsing fails
                  return (
                    <div className="rounded-lg border bg-card p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Info className="w-4 h-4 text-muted-foreground" />
                        <h4 className="font-semibold text-sm">About</h4>
                      </div>
                      <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">
                        {business.about}
                      </p>
                    </div>
                  );
                }
                return null;
              })()}

            {/* Popular Times */}
            {business.popularTimes && (
              <div className="rounded-lg border bg-card p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className="w-4 h-4 text-muted-foreground" />
                  <h4 className="font-semibold text-sm">Popular Times</h4>
                </div>
                <p className="text-sm text-muted-foreground">{business.popularTimes}</p>
              </div>
            )}

            {/* Commerce Links */}
            {(business.reservations || business.orderOnline || business.menu) && (
              <div className="rounded-lg border bg-card p-4">
                <h4 className="font-semibold text-sm mb-3">Quick Actions</h4>
                <div className="flex flex-wrap gap-2">
                  {business.reservations && (
                    <a
                      href={business.reservations}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-sm font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Calendar className="w-4 h-4" />
                      Make Reservation
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                  {business.orderOnline && (
                    <a
                      href={business.orderOnline}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors text-sm font-medium"
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
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border bg-secondary text-secondary-foreground hover:bg-secondary/90 transition-colors text-sm font-medium"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View Menu
                      <ExternalLink className="w-3 h-3" />
                    </a>
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
                  referrerPolicy="no-referrer"
                  crossOrigin="anonymous"
                  onError={(e) => {
                    console.error("Thumbnail failed to load:", business.thumbnail);
                    e.currentTarget.style.display = "none";
                  }}
                />
              </div>
            )}

            {/* Image Gallery */}
            {(() => {
              // Parse images - handle various formats
              let imageArray: string[] = [];

              if (business.images && Array.isArray(business.images)) {
                imageArray = business.images
                  .map((item: any) => {
                    if (typeof item === "string") {
                      // Try multiple parsing strategies

                      // Strategy 1: Direct URL
                      if (item.startsWith("http://") || item.startsWith("https://")) {
                        return item;
                      }

                      // Strategy 2: Try to extract URL using regex (in case JSON is malformed)
                      const urlMatch = item.match(/https?:\/\/[^\s"]+/);
                      if (urlMatch) {
                        return urlMatch[0];
                      }

                      // Strategy 3: Try JSON parsing with error handling
                      try {
                        const parsed = JSON.parse(item);
                        if (typeof parsed === "object" && parsed !== null) {
                          const url = parsed.image || parsed.url;
                          if (
                            url &&
                            typeof url === "string" &&
                            (url.startsWith("http://") || url.startsWith("https://"))
                          ) {
                            return url;
                          }
                        }
                      } catch (e) {
                        // JSON parse failed, already tried regex
                      }

                      return null;
                    } else if (item && typeof item === "object") {
                      const url = item.image || item.url;
                      if (
                        url &&
                        typeof url === "string" &&
                        (url.startsWith("http://") || url.startsWith("https://"))
                      ) {
                        return url;
                      }
                    }
                    return null;
                  })
                  .filter((url): url is string => url !== null);
              }

              if (imageArray.length > 0) {
                return (
                  <>
                    <div className="space-y-2">
                      <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                        <ImageIcon className="w-3 h-3" />
                        Photos ({imageArray.length})
                      </p>
                      <div className="grid grid-cols-2 gap-2">
                        {imageArray.slice(0, 4).map((image, i) => (
                          <a
                            key={i}
                            href={image}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="relative aspect-video rounded-lg overflow-hidden group border bg-muted"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <img
                              src={image}
                              alt={`${business.name} photo ${i + 1}`}
                              className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                              referrerPolicy="no-referrer"
                              crossOrigin="anonymous"
                            />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                              <ExternalLink className="w-4 h-4 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                            </div>
                          </a>
                        ))}
                      </div>
                      {imageArray.length > 4 && (
                        <button
                          onClick={() => setShowAllPhotos(true)}
                          className="text-xs text-primary hover:underline text-center w-full cursor-pointer"
                        >
                          +{imageArray.length - 4} more photos
                        </button>
                      )}
                    </div>

                    {/* All Photos Dialog */}
                    <Dialog open={showAllPhotos} onOpenChange={setShowAllPhotos}>
                      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
                        <DialogHeader>
                          <DialogTitle className="flex items-center gap-2">
                            <ImageIcon className="w-5 h-5" />
                            All Photos ({imageArray.length})
                          </DialogTitle>
                        </DialogHeader>
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
                          {imageArray.map((image, i) => (
                            <a
                              key={i}
                              href={image}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="relative aspect-video rounded-lg overflow-hidden group border bg-muted"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <img
                                src={image}
                                alt={`${business.name} photo ${i + 1}`}
                                className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                                referrerPolicy="no-referrer"
                                crossOrigin="anonymous"
                              />
                              <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                <ExternalLink className="w-4 h-4 text-white opacity-0 group-hover:opacity-100 transition-opacity" />
                              </div>
                            </a>
                          ))}
                        </div>
                      </DialogContent>
                    </Dialog>
                  </>
                );
              }

              return null;
            })()}

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
